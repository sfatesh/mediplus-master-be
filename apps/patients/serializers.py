from rest_framework import serializers
from django.utils import timezone
from .models import Patient, PatientConsent


class PatientConsentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientConsent
        fields = [
            'id',
            'patient',
            'consent_type',
            'status',
            'granted_at',
            'revoked_at',
            'signed_by',
            'witness_name',
            'notes',
        ]
        read_only_fields = ['id', 'patient', 'granted_at']


class PatientSerializer(serializers.ModelSerializer):
    consents = PatientConsentSerializer(many=True, read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Patient
        fields = [
            'id',
            'user',
            'user_email',
            'medical_record_number',
            'first_name',
            'last_name',
            'date_of_birth',
            'gender',
            'blood_group',
            'phone',
            'email',
            'address',
            'city',
            'postal_code',
            'emergency_contact_name',
            'emergency_contact_phone',
            'emergency_contact_relationship',
            'guardian_name',
            'guardian_relationship',
            'guardian_phone',
            'allergies',
            'medical_history',
            'is_active',
            'consents',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'medical_record_number', 'user', 'created_at', 'updated_at']

    def validate(self, attrs):
        first_name = attrs.get('first_name', getattr(self.instance, 'first_name', '')).strip()
        last_name = attrs.get('last_name', getattr(self.instance, 'last_name', '')).strip()
        phone = attrs.get('phone', getattr(self.instance, 'phone', '')).strip()
        email = attrs.get('email', getattr(self.instance, 'email', None))
        dob = attrs.get('date_of_birth', getattr(self.instance, 'date_of_birth', None))

        # Duplicate detection check
        query = Patient.objects.filter(is_active=True)
        if self.instance:
            query = query.exclude(pk=self.instance.pk)

        duplicate = None
        # 1. Match by email
        if email and email.strip():
            duplicate = query.filter(email__iexact=email.strip()).first()

        # 2. Match by exact phone and Date of Birth
        if not duplicate and phone and dob:
            duplicate = query.filter(phone=phone, date_of_birth=dob).first()

        # 3. Match by full name and Date of Birth
        if not duplicate and first_name and last_name and dob:
            duplicate = query.filter(
                first_name__iexact=first_name,
                last_name__iexact=last_name,
                date_of_birth=dob
            ).first()

        if duplicate:
            raise serializers.ValidationError({
                "duplicate": f"Possible duplicate patient detected with MRN {duplicate.medical_record_number} ({duplicate.full_name})."
            })

        return attrs

    def create(self, validated_data):
        if not validated_data.get('medical_record_number'):
            year = timezone.now().year
            last_patient = Patient.objects.order_by('-id').first()
            seq = (last_patient.id + 1) if last_patient else 1
            validated_data['medical_record_number'] = f"MED-{year}-{seq:04d}"
        return super().create(validated_data)


class PatientDuplicateCheckSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
