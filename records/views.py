from __future__ import annotations

import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from extractor import ExtractionError

from .exports import EXPORT_HEADERS, presentation_values, workbook_bytes
from .forms import ManualRecordForm, PresentationEditForm, UploadLettersForm
from .models import Letter, Presentation
from .selectors import dashboard_metrics, filtered_presentations
from .services import persist_preview, prepare_preview
from .use_cases import create_manual_record, delete_cpc_letter, update_presentation


@login_required
def dashboard(request):
    records, query, result = filtered_presentations(request.GET)
    context = {
        "records": records,
        "query": query,
        "selected_result": result,
        **dashboard_metrics(),
    }
    return render(request, "records/dashboard.html", context)


@login_required
def upload_letters(request):
    preview = request.session.get("upload_preview")
    if request.method == "POST":
        form = UploadLettersForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                preview = prepare_preview(form.cleaned_data["files"])
                request.session["upload_preview"] = preview
                request.session.modified = True
                return render(
                    request,
                    "records/upload.html",
                    {"form": UploadLettersForm(), "preview": preview},
                )
            except (ExtractionError, IntegrityError, ValueError) as error:
                messages.error(request, str(error))
    else:
        form = UploadLettersForm()
    return render(request, "records/upload.html", {"form": form, "preview": preview})


@login_required
def confirm_upload(request):
    if request.method != "POST":
        return redirect("upload_letters")
    preview = request.session.get("upload_preview")
    if not preview:
        messages.error(request, "La vista previa expiró. Vuelve a cargar los archivos.")
        return redirect("upload_letters")
    try:
        persist_preview(preview, request.POST, request.user)
    except (ExtractionError, IntegrityError, ValidationError, ValueError) as error:
        messages.error(request, str(error))
        return render(
            request,
            "records/upload.html",
            {"form": UploadLettersForm(), "preview": preview},
        )
    request.session.pop("upload_preview", None)
    messages.success(request, "Las cartas y sus equipos se guardaron correctamente.")
    return redirect("dashboard")


@login_required
def manual_record(request):
    form = ManualRecordForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            create_manual_record(data, request.user)
        except (IntegrityError, ValidationError) as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Registro manual guardado.")
            return redirect("dashboard")
    return render(request, "records/manual.html", {"form": form})


@login_required
def edit_presentation(request, pk):
    presentation = get_object_or_404(
        Presentation.objects.select_related(
            "cpc_letter", "equipment", "evaluation", "evaluation__response_letter"
        ),
        pk=pk,
    )
    form = PresentationEditForm.from_presentation(
        presentation, request.POST or None, request.FILES or None
    )
    if request.method == "POST" and form.is_valid():
        try:
            update_presentation(presentation, form.cleaned_data, request.user)
        except (IntegrityError, ValidationError) as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Registro actualizado.")
            return redirect("dashboard")
    return render(
        request,
        "records/edit.html",
        {"form": form, "presentation": presentation},
    )


@login_required
def delete_letter(request, pk):
    letter = get_object_or_404(Letter, pk=pk, direction=Letter.Direction.CPC_AAM)
    if request.method == "POST":
        number = delete_cpc_letter(letter, request.user)
        messages.success(request, f"La carta {number} y todos sus datos fueron eliminados.")
        return redirect("dashboard")
    return render(request, "records/delete.html", {"letter": letter})


@login_required
def export_csv(request):
    records, _, _ = filtered_presentations(request.GET)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="registros-krys.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(EXPORT_HEADERS)
    for record in records:
        writer.writerow(presentation_values(record))
    return response


@login_required
def export_xlsx(request):
    records, _, _ = filtered_presentations(request.GET)
    response = HttpResponse(
        workbook_bytes(records),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="registros-krys.xlsx"'
    return response
