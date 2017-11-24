from django.shortcuts import get_object_or_404, render
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.decorators import user_passes_test
from easy_pdf.rendering import render_to_pdf_response

from .models import AccessCode, Choice, Question, Vote, OpenQuestion


def index(request):
    return render(request, 'polls/index.html',
                  {'questions_list': Question.objects.order_by('-end_date',
                                                               '-start_date')})


def detail(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    if question.start_date > timezone.now() \
       or question.end_date < timezone.now():
        return render(request, 'polls/detail.html', {
            'question': question, 'error': "Głosowanie nie jest aktywne"})
    try:
        openQuestion = OpenQuestion.objects.get(pk=question_id)
    except OpenQuestion.DoesNotExist:
        return render(request, 'polls/detail.html', {'question': question})
    return render(request, 'polls/detail.html',
                  {'question': openQuestion, 'is_open': True})


def result(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    if timezone.now() < question.end_date:
        return render(request, 'polls/result.html',
                      {'error': 'Głosowanie jeszcze się nie zakończyło'})

    choices = Choice.objects.filter(
        question__exact=question).order_by('-votes')
    codes = []
    for code in question.accesscode_set.all():
        last_choice = Vote.objects.filter(
            question__exact=question, code__exact=code).last()
        if last_choice:
            last_choice = last_choice.choice.choice_text
        else:
            last_choice = '-'
        codes.append({'code': code.code, 'num_of_votes': code.counter,
                      'last_choice': last_choice})

    return render(request, 'polls/result.html', 
                  {'question': question,
                   'choices': choices,
                   'codes': codes,
                   'success': is_vote_successful(question)})


def is_vote_successful(question):
    codes = question.get_codes()
    used_codes = Vote.objects.filter(
        question__exact=question).values(
        'code').distinct()
    if len(used_codes) / len(codes) * 100 < 50:
        return False
    else:
        return True


def vote(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    if question.start_date > timezone.now() \
       or question.end_date < timezone.now():
        return render(request,
                      'polls/detail.html',
                      {'question': question,
                       'error': "Głosowanie nie jest aktywne"})

    code = request.POST['code']
    if code == '' or not question.is_code_correct(code):
        return render(request,
                      'polls/detail.html',
                      {'question': question,
                       'error': "Niewłaściwy kod uwierzytelniający"})

    choice = request.POST.get('choice', None)
    new_choice = request.POST.get('new_choice', '')
    if(choice and new_choice != ''):
        return render(
            request,
            'polls/detail.html',
            {
                'question': question,
                'error': "Nie można głosować na istniejącą odpowiedź i \
                          jednocześnie proponować nową"})

    if not choice and new_choice == '':
        return render(request, 'polls/detail.html',
                      {
                          'question': question,
                          'error': "Nie wybrano odpowiedzi"})

    if choice:
        if question.choice_set.filter(pk=choice).exists():
            choice = question.choice_set.get(pk=choice)
        else:
            return render(
                request, 'polls/detail.html',
                {'question': question, 'error': "Odpowiedź nie istnieje"})

    if not choice and OpenQuestion.objects.filter(pk=question.pk).exists():
        choice = Choice.objects.create(
            question=question, choice_text=new_choice)

    code = AccessCode.objects.get(question=question, code=code)
    prev_vote = Vote.objects.filter(
        question__exact=question, code__exact=code).last()
    if prev_vote:
        prev_vote.choice.votes -= 1
        prev_vote.choice.save()

    choice = Choice.objects.get(pk=choice.id)
    choice.votes += 1
    choice.save()
    code.counter += 1
    code.save()
    Vote.objects.create(question=question, choice=choice, code=code)
    return HttpResponseRedirect(reverse('polls:index'))


@user_passes_test(lambda u: u.is_superuser)
def codes(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    return render(request, 'polls/codesList.html',
                  {"codes_dict": question.get_codes()})


@user_passes_test(lambda u: u.is_superuser)
def codes_pdf(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    return render_to_pdf_response(request, 'polls/codesList.html',
                                  {"codes_dict": question.get_codes()})
