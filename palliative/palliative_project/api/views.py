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
            status = 'Stable' # Default
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
            
            # Special case: Restocking (adding to existing count)
            if 'add_stock' in data:
                try:
                    val = int(data['add_stock'])
                    if val > 0:
                        item.count += val
                        item.save()
                        return JsonResponse({"message": f"Restocked successfully. New total: {item.count}"})
                except ValueError:
                    return JsonResponse({"error": "Invalid stock value"}, status=400)

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

# --- Export Functionality ---
import openpyxl
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from django.http import HttpResponse

@csrf_exempt
def export_patients(request):
    """
    GET: Export patients to Excel/PDF with filters
    """
    if request.method == 'GET':
        # 1. Base Query
        queryset = Patient.objects.all()

        # 2. Apply Filters (Same logic as frontend, but in Python)
        search = request.GET.get('search', '').lower()
        if search:
            queryset = queryset.filter(full_name__icontains=search) | queryset.filter(id__icontains=search)

        status = request.GET.get('status', '')
        if status:
            if status == 'Alive':
                queryset = queryset.filter(is_expired=False)
            elif status == 'Dead':
                queryset = queryset.filter(is_expired=True)
            elif status == 'Stable':
                # Active or Stable
                queryset = queryset.filter(current_status__in=['Active', 'Stable'], is_expired=False)
            elif status == 'Bedridden':
                queryset = queryset.filter(condition='Bedridden', is_expired=False)
            elif status == 'Not Bedridden':
                queryset = queryset.filter(condition='Not Bedridden', is_expired=False)
            else:
                # Moderate / Severe
                queryset = queryset.filter(current_status=status, is_expired=False)
        
        # Age Range
        try:
            min_age = int(request.GET.get('min_age', 0))
            max_age = int(request.GET.get('max_age', 150))
            queryset = queryset.filter(age__gte=min_age, age__lte=max_age)
        except:
            pass # Ignore invalid age input

        # Disease & Material (Basic string match if provided)
        disease = request.GET.get('disease', '')
        if disease:
            queryset = queryset.filter(disease=disease)
        
        # Note: Material filtering in backend would require complex join on Allocation
        # For simplicity, if material is passed, we might skip implementation or do a subquery
        # Here we will implement basic material check if needed:
        material = request.GET.get('material', '')
        if material:
             queryset = queryset.filter(allocations__material_name=material).distinct()

        # 3. sorting (Expired at bottom, then ID desc)
        # Using sorted() for complex sort logic similar to JS
        patients = list(queryset)
        patients.sort(key=lambda p: (p.is_expired, -p.id))

        export_format = request.GET.get('format', 'excel')

        if export_format == 'excel':
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = 'attachment; filename="patients_export.xlsx"'
            
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Patients"

            # Headers
            headers = ['ID', 'Name', 'Age', 'Gender', 'Condition', 'Status', 'Disease', 'Allocated Items']
            ws.append(headers)

            for p in patients:
                # Get materials string
                mats = ", ".join([a.material_name for a in p.allocations.all()])
                
                # Normalize Status (Active -> Stable)
                raw_status = p.current_status
                if raw_status == 'Active':
                    raw_status = 'Stable'
                
                status_display = "Expired" if p.is_expired else raw_status
                
                ws.append([
                    p.id, p.full_name, p.age, p.gender, 
                    p.condition, status_display, p.disease, mats
                ])
            
            wb.save(response)
            return response

        elif export_format == 'pdf':
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="patients_export.pdf"'
            
            p = canvas.Canvas(response, pagesize=letter)
            width, height = letter
            y = height - 50

            p.setFont("Helvetica-Bold", 16)
            p.drawString(50, y, "Patient Registry Export")
            y -= 30
            
            p.setFont("Helvetica-Bold", 10)
            headers = ["ID", "Name", "Age", "Condition", "Status"]
            x_positions = [50, 100, 250, 300, 450]
            
            for i, h in enumerate(headers):
                p.drawString(x_positions[i], y, h)
            
            y -= 20
            p.setFont("Helvetica", 10)

            for pat in patients:
                if y < 50:
                    p.showPage()
                    y = height - 50
                
                # Normalize Status
                raw_status = pat.current_status
                if raw_status == 'Active':
                    raw_status = 'Stable'
                
                status_display = "Expired" if pat.is_expired else raw_status
                
                p.drawString(x_positions[0], y, str(pat.id))
                p.drawString(x_positions[1], y, pat.full_name[:25]) # Truncate name
                p.drawString(x_positions[2], y, str(pat.age))
                p.drawString(x_positions[3], y, pat.condition)
                p.drawString(x_positions[4], y, status_display)
                y -= 15
            
            p.showPage()
            p.save()
            return response

    return JsonResponse({"error": "Invalid request"}, status=400)

@csrf_exempt
def export_visits(request):
    """
    GET: Export visits (filtered) to Excel/PDF
    """
    if request.method == 'GET':
        # 1. Base Query
        visits = Visit.objects.select_related('patient').all()
        
        # 2. Filtering (Match Frontend Logic: effective_date = scheduled_date || visit_date)
        date_filter = request.GET.get('date')
        month_filter = request.GET.get('month')
        
        filtered_visits = []
        for v in visits:
            # Determine effective date (string format YYYY-MM-DD)
            eff_date = v.scheduled_date or v.visit_date
            if not eff_date:
                continue
            
            eff_date_str = str(eff_date)
            
            # Apply Filter
            if date_filter:
                if eff_date_str != date_filter:
                    continue
            elif month_filter:
                if not eff_date_str.startswith(month_filter):
                    continue
            
            filtered_visits.append(v)
            
        # 3. Sort (Date desc)
        filtered_visits.sort(key=lambda x: (x.scheduled_date or x.visit_date), reverse=True)
        
        export_format = request.GET.get('format', 'excel')
        
        if export_format == 'excel':
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = 'attachment; filename="visits_export.xlsx"'
            
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Visits"
            
            headers = ['Date', 'Patient Name', 'Service', 'Condition', 'Status', 'Time Spent']
            ws.append(headers)
            
            for v in filtered_visits:
                status = "Completed" if v.is_completed else "Scheduled"
                eff_date = v.scheduled_date or v.visit_date
                
                # Normalize Active -> Stable
                cond = v.condition_assessment
                if cond == 'Active': cond = 'Stable'
                
                ws.append([
                    eff_date, v.patient.full_name, v.service_performed,
                    cond, status, v.time_spent
                ])
            
            wb.save(response)
            return response
            
        elif export_format == 'pdf':
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="visits_export.pdf"'
            
            p = canvas.Canvas(response, pagesize=letter)
            width, height = letter
            y = height - 50
            
            p.setFont("Helvetica-Bold", 16)
            p.drawString(50, y, "Visits Report")
            y -= 30
            
            p.setFont("Helvetica-Bold", 10)
            # Table Headers
            p.drawString(50, y, "Date")
            p.drawString(130, y, "Patient")
            p.drawString(250, y, "Service")
            p.drawString(400, y, "Status")
            p.drawString(500, y, "Condition")
            
            y -= 20
            p.setFont("Helvetica", 10)
            
            for v in filtered_visits:
                if y < 50:
                    p.showPage()
                    y = height - 50
                
                status = "Completed" if v.is_completed else "Scheduled"
                eff_date = str(v.scheduled_date or v.visit_date)
                
                 # Normalize Active -> Stable
                cond = v.condition_assessment or '-'
                if cond == 'Active': cond = 'Stable'
                
                patient_name = v.patient.full_name[:20]
                service = (v.service_performed or '-')[:25]
                
                p.drawString(50, y, eff_date)
                p.drawString(130, y, patient_name)
                p.drawString(250, y, service)
                p.drawString(400, y, status)
                p.drawString(500, y, cond)
                y -= 15
                
            p.showPage()
            p.save()
            return response

    return JsonResponse({"error": "Method not allowed"}, status=405)
