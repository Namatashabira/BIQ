from django.shortcuts import render
from django.http import HttpResponse

def marks_entry(request):
    return render(request, 'schools/marks_entry.html')

def fees_page(request):
    return render(request, 'schools/fees_page.html')