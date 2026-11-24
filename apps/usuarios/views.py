from django.conf import settings
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import LoginView
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.views import View

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import Group
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView

from .forms import CodigoVerificacionForm, LoginForm, UsuarioCreateForm, UsuarioUpdateForm
from .models import CodigoVerificacion, Usuario

SESSION_KEY_2FA = 'usuario_pendiente_2fa'
SESSION_KEY_2FA_NEXT = 'usuario_pendiente_2fa_next'


class LoginConDobleFactorView(LoginView):
    template_name = 'usuarios/login.html'
    form_class = LoginForm

    def form_valid(self, form):
        usuario = form.get_user()
        next_url = self.get_success_url()
        codigo = CodigoVerificacion.generar_para(usuario)
        send_mail(
            'Código de verificación - Farmacia Privada',
            f'Tu código de acceso es {codigo.codigo}. Vence en '
            f'{CodigoVerificacion.VIGENCIA_MINUTOS} minutos.',
            None,
            [usuario.email],
        )
        # Si ya había otra sesión activa en este navegador, se cierra
        # antes de dejar pendiente el 2FA: mientras se verifica el código
        # no debe quedar autenticado como el usuario anterior.
        auth_logout(self.request)
        self.request.session[SESSION_KEY_2FA] = usuario.pk
        self.request.session[SESSION_KEY_2FA_NEXT] = next_url
        return redirect('usuarios:verificar_codigo')


class VerificarCodigoView(View):
    template_name = 'usuarios/verificar_codigo.html'

    def get(self, request):
        if SESSION_KEY_2FA not in request.session:
            return redirect('usuarios:login')
        return render(request, self.template_name, {'form': CodigoVerificacionForm()})

    def post(self, request):
        usuario_id = request.session.get(SESSION_KEY_2FA)
        if not usuario_id:
            return redirect('usuarios:login')

        form = CodigoVerificacionForm(request.POST)
        if form.is_valid():
            codigo = (
                CodigoVerificacion.objects
                .filter(usuario_id=usuario_id, codigo=form.cleaned_data['codigo'])
                .order_by('-creado')
                .first()
            )
            if codigo and codigo.vigente():
                codigo.usado = True
                codigo.save(update_fields=['usado'])
                usuario = Usuario.objects.get(pk=usuario_id)
                auth_login(request, usuario)
                del request.session[SESSION_KEY_2FA]
                next_url = request.session.pop(SESSION_KEY_2FA_NEXT, settings.LOGIN_REDIRECT_URL)
                return redirect(next_url)
            form.add_error('codigo', 'Código inválido o expirado.')

        return render(request, self.template_name, {'form': form})


@login_required
def cambiar_contrasena(request):
    """Permite a cualquier usuario autenticado cambiar su propia contraseña."""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)   # Mantiene la sesión activa
            from django.contrib import messages
            messages.success(request, 'Contraseña actualizada correctamente.')
            return redirect('panel:inicio')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'usuarios/cambiar_contrasena.html', {'form': form})


class UsuarioListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Usuario
    template_name = 'usuarios/usuario_lista.html'
    context_object_name = 'usuarios'
    permission_required = 'usuarios.view_usuario'
    paginate_by = 20

    def get_queryset(self):
        qs = Usuario.objects.all().order_by('-date_joined')
        
        busqueda = self.request.GET.get('q', '').strip()
        if busqueda:
            qs = qs.filter(
                Q(rut__icontains=busqueda) | 
                Q(first_name__icontains=busqueda) |
                Q(last_name__icontains=busqueda) |
                Q(email__icontains=busqueda)
            )

        rol = self.request.GET.get('rol')
        if rol:
            qs = qs.filter(rol=rol)
            
        return qs

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            'filtros': self.request.GET,
            'roles': Usuario.Rol.choices,
        }


class UsuarioCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Usuario
    form_class = UsuarioCreateForm
    template_name = 'usuarios/usuario_form.html'
    success_url = reverse_lazy('usuarios:lista')
    permission_required = 'usuarios.add_usuario'

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'titulo': 'Nuevo Usuario'}

    def form_valid(self, form):
        usuario = form.save(commit=False)
        # Set a random strong password for the new user initially.
        # En la vida real se mandaría un correo o se dejaría que el usuario la cambie,
        # para este proyecto pondremos el mismo RUT como clave inicial.
        usuario.set_password(usuario.rut)
        usuario.username = usuario.rut  # Usamos el RUT como username interno
        usuario.save()
        # The form's save() method will be called again in super().form_valid(form)
        # but wait, super().form_valid(form) calls form.save(), which saves again.
        # We should just return super().form_valid(form) but setting the password first.
        # Actually form_valid calls form.save(). Let's just do it directly.
        messages.success(self.request, f'Usuario {usuario.get_full_name()} creado. Clave temporal: {usuario.rut}')
        return super().form_valid(form)


class UsuarioUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Usuario
    form_class = UsuarioUpdateForm
    template_name = 'usuarios/usuario_form.html'
    success_url = reverse_lazy('usuarios:lista')
    permission_required = 'usuarios.change_usuario'

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'titulo': 'Editar Usuario'}

    def form_valid(self, form):
        usuario = form.save(commit=False)
        if usuario.rut != usuario.username:
            usuario.username = usuario.rut
        usuario.save()
        messages.success(self.request, f'Datos de {usuario.get_full_name()} actualizados.')
        return super().form_valid(form)


class GrupoListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Muestra los roles predefinidos y sus permisos."""
    model = Group
    template_name = 'usuarios/grupo_lista.html'
    context_object_name = 'grupos'
    permission_required = 'auth.view_group'
    
    def get_queryset(self):
        return Group.objects.prefetch_related('permissions').all().order_by('name')
