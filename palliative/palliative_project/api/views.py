from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.forms.models import model_to_dict
from django.db import models
from django.db.models import Count
from .models import Patient, Visit, MaterialAllocation, Inventory
import json
from django.shortcuts import get_object_or_404
from deep_translator import GoogleTranslator

@csrf_exempt
def translate_text(request):
    """
    POST: Translate Malayalam text to English
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            text = data.get('text', '')
            if not text:
                return JsonResponse({"translated": ""})
            
            translated = GoogleTranslator(source='ml', target='en').translate(text)
            return JsonResponse({"translated": translated})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"error": "Method not allowed"}, status=405)

@csrf_exempt
def visit_detail(request, pk):
    """
    GET: Get visit details
    PUT: Update visit (e.g., complete it)
    """
    visit = get_object_or_404(Visit, pk=pk)

    if request.method == 'GET':
        data = model_to_dict(visit)
        data['id'] = visit.id
        # Add patient name for display
        data['patient_name'] = visit.patient.full_name
        return JsonResponse(data)

    elif request.method == 'PUT':
        try:
            data = json.loads(request.body)
            for field, value in data.items():
                if hasattr(visit, field):
                    setattr(visit, field, value)
            visit.save()
            return JsonResponse({"message": "Visit updated successfully!"})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

@csrf_exempt
def patient_list(request):
    """
    GET: List all patients
    POST: Create a new patient
    """
    if request.method == 'GET':
        patients_qs = Patient.objects.prefetch_related('allocations').all()
        patients_data = []
        for p in patients_qs:
            # Get active (not returned) material names
            active_allocs = [a.material_name for a in p.allocations.all() if not a.return_date]
            p_dict = model_to_dict(p)
            p_dict['allocations'] = active_allocs
            patients_data.append(p_dict)
            
        return JsonResponse(patients_data, safe=False)

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            try:
                age = int(data.get('age'))
            except (ValueError, TypeError):
                return JsonResponse({"error": "Invalid Age"}, status=400)
                
            # Map 'condition' from form (Stable/Moderate/Severe) to 'current_status' if it matches
            input_condition = data.get('condition')
            status = 'Active' # Default
            if input_condition in ['Stable', 'Moderate', 'Severe', 'Critical', 'Bedridden']:
                status = input_condition
                # If Status is Bedridden, put it in condition field as well roughly, or keep separate?
                # User form sends 'Stable' options as 'condition'.
            
            patient = Patient.objects.create(
                full_name=data.get('full_name'),
                gender=data.get('gender'),
                dob=data.get('dob'),
                age=age,
                address=data.get('address'),
                condition=data.get('condition'), # Keep original value here too
                current_status=status,           # Set status explicitly
                disease=data.get('disease'),
                guardian_name=data.get('guardian_name'),
                guardian_phone=data.get('guardian_phone'),
                relative_name=data.get('relative_name', '')
            )
            return JsonResponse({"message": "Patient registered successfully!", "id": patient.id}, status=201)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
            
    return JsonResponse({"error": "Method not allowed"}, status=405)

@csrf_exempt
def patient_detail(request, pk):
    """
    GET: Retrieve single patient
    PUT: Update patient details
    """
    patient = get_object_or_404(Patient, pk=pk)
    
    if request.method == 'GET':
        return JsonResponse(model_to_dict(patient))
    
    elif request.method == 'PUT':
        try:
            data = json.loads(request.body)
            for field, value in data.items():
                if hasattr(patient, field):
                    setattr(patient, field, value)
            patient.save()
            return JsonResponse({"message": "Patient updated successfully!"})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

@csrf_exempt
def visit_list(request, patient_id=None):
    """
    GET: List visits (if patient_id provided, filter by it. If not, list ALL visits)
    POST: Add a new visit
    """
    # Helper to serialize visits with patient names
    def serialize_visits(queryset):
        results = []
        for v in queryset:
            d = model_to_dict(v)
            d['id'] = v.id  # Explicitly add ID
            d['patient_name'] = v.patient.full_name
            results.append(d)
        return results

    if request.method == 'GET':
        if patient_id:
            visits = Visit.objects.filter(patient_id=patient_id).order_by('-scheduled_date')
        else:
            # List ALL visits (for the main dashboard)
            visits = Visit.objects.all().order_by('-scheduled_date')
        
        return JsonResponse(serialize_visits(visits), safe=False)
        
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            # Support creating visit without patient_id in URL if it's in body
            pid = patient_id if patient_id else data.get('patient_id')
            
            visit = Visit.objects.create(
                patient_id=pid,
                scheduled_date=data.get('scheduled_date'),
                # Optional fields for direct completion
                service_performed=data.get('service_performed'),
                condition_assessment=data.get('condition_assessment')
            )
            return JsonResponse({"message": "Visit scheduled successfully!", "id": visit.id}, status=201)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

@csrf_exempt
def allocation_list(request, patient_id):
    """
    GET: List material allocations for a patient
    POST: Allocate new material
    """
    if request.method == 'GET':
        allocations = list(MaterialAllocation.objects.filter(patient_id=patient_id).values())
        return JsonResponse(allocations, safe=False)
        
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Extract Inventory ID from material_name string "Name (Category)" or passed explicitly?
            # It's better to pass it explicitly from frontend, but we can try to extract or expect it in body.
            # Plan says: "Update to accept inventory_id"
            
            inventory_id = data.get('inventory_item_id') # Expecting this field
            print(f"Debug Allocation: inventory_id received = {inventory_id}")
            
            allocation = MaterialAllocation.objects.create(
                patient_id=patient_id,
                material_name=data.get('material_name'),
                inventory_item_id=inventory_id,
                allocation_date=data.get('allocation_date'),
                is_returnable=data.get('is_returnable', False),
                return_date=data.get('return_date'),
                is_damaged=data.get('is_damaged', False)
            )
            return JsonResponse({"message": "Material allocated successfully!"}, status=201)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

@csrf_exempt
def get_analytics(request):
    """
    GET: Retrieve aggregated analytics data
    """
    if request.method == 'GET':
        total_patients = Patient.objects.count()
        
        # Status Counts
        active = Patient.objects.filter(current_status='Active', is_expired=False).count()
        moderate = Patient.objects.filter(current_status='Moderate', is_expired=False).count()
        severe = Patient.objects.filter(current_status='Severe', is_expired=False).count()
        expired = Patient.objects.filter(is_expired=True).count()
        
        # Disease Distribution
        diseases = Patient.objects.values('disease').annotate(count=models.Count('disease'))
        disease_data = {d['disease']: d['count'] for d in diseases}
        
        # Age Groups
        age_groups = {
            '0-18': Patient.objects.filter(age__lte=18).count(),
            '19-40': Patient.objects.filter(age__gt=18, age__lte=40).count(),
            '41-60': Patient.objects.filter(age__gt=40, age__lte=60).count(),
            '60+': Patient.objects.filter(age__gt=60).count()
        }
        
        data = {
            'total': total_patients,
            'status': {
                'active': active,
                'moderate': moderate,
                'severe': severe,
                'expired': expired
            },
            'disease_distribution': disease_data,
            'age_groups': age_groups
        }
        
        return JsonResponse(data)
    
@csrf_exempt
def inventory_list(request):
    """
    GET: List all inventory items
    POST: Add new item
    """
    if request.method == 'GET':
        items = list(Inventory.objects.values())
        return JsonResponse(items, safe=False)
    
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            item = Inventory.objects.create(
                item_name=data.get('item_name'),
                category=data.get('category'),
                count=int(data.get('count', 0)),
                description=data.get('description', '')
            )
            return JsonResponse({"message": "Item added successfully!", "id": item.id}, status=201)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"error": "Method not allowed"}, status=405)

@csrf_exempt
def inventory_detail(request, pk):
    """
    PUT: Update inventory item (e.g. stock count)
    GET: Get detailed info
    """
    item = get_object_or_404(Inventory, pk=pk)
    
    if request.method == 'GET':
        return JsonResponse(model_to_dict(item))
    
    elif request.method == 'PUT':
        try:
            data = json.loads(request.body)
            for field, value in data.items():
                if hasattr(item, field):
                    setattr(item, field, value)
            item.save()
            return JsonResponse({"message": "Inventory updated successfully!"})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"error": "Method not allowed"}, status=405)

@csrf_exempt
def allocation_detail(request, pk):
    """
    PUT: Update allocation (e.g., mark as returned)
    """
    allocation = get_object_or_404(MaterialAllocation, pk=pk)

    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
            
            # Check for return action
            if 'return_date' in data and data['return_date']:
                allocation.return_date = data['return_date']
                allocation.is_damaged = data.get('is_damaged', False)
                
                # Logic: If returnable, not previously returned, and not damaged -> Restock
                print(f"Debug Return: is_returnable={allocation.is_returnable}, is_damaged={allocation.is_damaged}, inventory_item={allocation.inventory_item}")
                if allocation.is_returnable and not allocation.is_damaged:
                     if allocation.inventory_item:
                         allocation.inventory_item.count += 1
                         allocation.inventory_item.save()
                         print(f"Debug: Stock incremented for {allocation.inventory_item.item_name}")
                     else:
                         print("Debug: No inventory item linked!")
            
            allocation.save()
            return JsonResponse({"message": "Allocation updated successfully!"})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
    
    return JsonResponse({"error": "Method not allowed"}, status=405)

@csrf_exempt
def inventory_history(request, pk):
    """
    GET: Get full history and stats for an inventory item
    """
    item = get_object_or_404(Inventory, pk=pk)
    
    if request.method == 'GET':
        # 1. Direct Link (New Data)
        allocations = MaterialAllocation.objects.filter(inventory_item=item)
        
        # 2. String Match (Legacy Data fallback)
        # Search for name in "Item Name (Category)" format or just "Item Name"
        legacy_allocs = MaterialAllocation.objects.filter(
            inventory_item__isnull=True, 
            material_name__icontains=item.item_name
        )
        
        # Merge QuerySets
        all_allocs = (allocations | legacy_allocs).distinct().order_by('-allocation_date')
        
        history = []
        stats = {
            "total_allocated": all_allocs.count(),
            "returned_good": 0,
            "returned_damaged": 0,
            "with_patient": 0
        }
        
        for alloc in all_allocs:
            history.append({
                "patient_name": alloc.patient.full_name,
                "allocation_date": alloc.allocation_date,
                "return_date": alloc.return_date,
                "is_damaged": alloc.is_damaged,
                "is_returnable": alloc.is_returnable
            })
            
            if alloc.return_date:
                if alloc.is_damaged:
                    stats["returned_damaged"] += 1
                else:
                    stats["returned_good"] += 1
            else:
                 # Only count as "with patient" if it IS returnable and NOT returned
                 if alloc.is_returnable:
                     stats["with_patient"] += 1

        return JsonResponse({
            "item": model_to_dict(item),
            "stats": stats,
            "history": history
        })
        
    return JsonResponse({"error": "Method not allowed"}, status=405)
