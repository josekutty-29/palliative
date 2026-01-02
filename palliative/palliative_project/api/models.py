from django.db import models

class Patient(models.Model):
    # Core Details
    full_name = models.CharField(max_length=200)
    gender = models.CharField(max_length=20, choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')])
    dob = models.DateField()
    age = models.IntegerField()
    address = models.TextField()
    
    # Medical Details
    condition = models.CharField(max_length=50, choices=[('Bedridden', 'Bedridden'), ('Not Bedridden', 'Not Bedridden')])
    disease = models.CharField(max_length=200)
    
    # Status
    is_expired = models.BooleanField(default=False)
    current_status = models.CharField(max_length=50, default='Active', choices=[('Active', 'Active'), ('Stable', 'Stable'), ('Moderate', 'Moderate'), ('Severe', 'Severe')])

    # Registration Info
    registration_date = models.DateField(auto_now_add=True)
    
    # Guardian / Contact
    guardian_name = models.CharField(max_length=200)
    guardian_phone = models.CharField(max_length=15)
    relative_name = models.CharField(max_length=200, blank=True, null=True, help_text="Relative staying with patient")

    def __str__(self):
        return f"{self.id} - {self.full_name}"

class Visit(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='visits')
    
    # Scheduling & Timing
    scheduled_date = models.DateField(null=True, blank=True)
    visit_date = models.DateField(null=True, blank=True) # Actual date of visit
    time_spent = models.CharField(max_length=50, blank=True, null=True)
    is_completed = models.BooleanField(default=False)
    
    # Details
    service_performed = models.TextField(blank=True, null=True)
    condition_assessment = models.CharField(max_length=50, blank=True, null=True, choices=[('Active', 'Active'), ('Moderate', 'Moderate'), ('Severe', 'Severe')])
    
    # Bilingual Voice Data
    symptoms_malayalam = models.TextField(blank=True, null=True)
    symptoms_english = models.TextField(blank=True, null=True)
    notes_malayalam = models.TextField(blank=True, null=True)
    notes_english = models.TextField(blank=True, null=True)
    
    def save(self, *args, **kwargs):
        # Auto-update patient status based on visit assessment
        super().save(*args, **kwargs)
        if self.condition_assessment:
            self.patient.current_status = self.condition_assessment
            self.patient.save()

class MaterialAllocation(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='allocations')
    material_name = models.CharField(max_length=200)
    inventory_item = models.ForeignKey('Inventory', on_delete=models.SET_NULL, null=True, blank=True)
    allocation_date = models.DateField()
    is_returnable = models.BooleanField(default=False)
    return_date = models.DateField(null=True, blank=True)
    is_damaged = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.material_name} for {self.patient.full_name}"

class Inventory(models.Model):
    item_name = models.CharField(max_length=200)
    category = models.CharField(max_length=50, choices=[('Government', 'Government'), ('Sponsorship', 'Sponsorship')])
    count = models.IntegerField(default=0)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.item_name} ({self.category})"
