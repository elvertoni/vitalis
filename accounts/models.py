"""User account models. Login is by email; there is no username field."""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel


class UserManager(BaseUserManager):
    """Creates users keyed by email instead of username."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('O e-mail é obrigatório.')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superusuário precisa de is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superusuário precisa de is_superuser=True.')
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    """Account holder. Owns every domain record through the ``user`` foreign key."""

    email = models.EmailField('e-mail', unique=True)
    full_name = models.CharField('nome completo', max_length=180)
    is_active = models.BooleanField('ativo', default=True)
    is_staff = models.BooleanField('acessa o admin', default=False)
    date_joined = models.DateTimeField('entrou em', default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    class Meta:
        verbose_name = 'usuário'
        verbose_name_plural = 'usuários'
        ordering = ['full_name']

    def __str__(self):
        return self.email

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.full_name.split(' ')[0] if self.full_name else self.email


class Profile(TimeStampedModel):
    """
    Personal and biometric data used by the nutrition and training calculations.

    Created automatically for every user by ``accounts.signals``, so the rest of the
    system can assume ``user.profile`` exists.
    """

    class Sex(models.TextChoices):
        MALE = 'M', 'Masculino'
        FEMALE = 'F', 'Feminino'
        OTHER = 'O', 'Outro'

    class NotificationChannel(models.TextChoices):
        EMAIL = 'email', 'E-mail'
        WHATSAPP = 'whatsapp', 'WhatsApp'
        PUSH = 'push', 'Notificação no navegador'

    user = models.OneToOneField(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='usuário',
    )
    birth_date = models.DateField('data de nascimento', null=True, blank=True)
    sex = models.CharField('sexo', max_length=1, choices=Sex.choices, blank=True)
    height_cm = models.PositiveSmallIntegerField(
        'altura (cm)',
        null=True,
        blank=True,
        help_text='Usada no cálculo de IMC e da meta calórica.',
    )
    phone = models.CharField('telefone', max_length=20, blank=True)
    notification_channel = models.CharField(
        'canal de lembrete',
        max_length=10,
        choices=NotificationChannel.choices,
        default=NotificationChannel.EMAIL,
    )
    target_weight_kg = models.DecimalField(
        'peso-alvo (kg)',
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Linha de meta no gráfico de evolução de peso. Em branco, o gráfico mostra só o real.',
    )

    class Meta:
        verbose_name = 'perfil'
        verbose_name_plural = 'perfis'

    def __str__(self):
        return f'Perfil de {self.user.email}'

    @property
    def age(self):
        """Age in whole years, or None when the birth date is unknown."""
        if not self.birth_date:
            return None
        today = timezone.localdate()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )
