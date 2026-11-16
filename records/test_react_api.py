import os
from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import Equipment, Letter, Presentation


class DashboardApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('react-test', password='test-password')
        letter = Letter.objects.create(full_number='CPC-0001', correlative=1, direction='CPC_AAM', letter_date=date(2026, 1, 1), created_by=self.user)
        equipment = Equipment.objects.create(code='ABC-123')
        Presentation.objects.create(cpc_letter=letter, equipment=equipment, equipment_type='Excavadora', created_by=self.user)

    def test_requires_login(self):
        self.assertEqual(self.client.get(reverse('dashboard_data')).status_code, 302)

    def test_records_and_filters(self):
        self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard_data'), {'q': 'ABC-123'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['metrics']['total'], 1)
        self.assertEqual(data['records'][0]['equipment'], 'ABC-123')
        self.assertEqual(data['records'][0]['resultLabel'], 'Pendiente')
        self.assertEqual(self.client.get(reverse('dashboard_data'), {'q': 'inexistente'}).json()['records'], [])

    def test_home_and_records_are_separate_and_legacy_filters_redirect(self):
        self.client.force_login(self.user)
        home = self.client.get(reverse('dashboard'))
        self.assertContains(home, 'Resumen general')
        self.assertNotContains(home, 'Historial de registros')
        records = self.client.get(reverse('records_list'), {'q': 'ABC-123'})
        self.assertContains(records, 'Historial de registros')
        self.assertContains(records, 'ABC-123')
        self.assertNotContains(records, 'Equipos activos por tipo')
        self.assertEqual(self.client.get(reverse('records_list'), HTTP_X_KS_CLIENT='react').json()['page'], 'records_list')
        old = self.client.get(reverse('dashboard'), {'q': 'ABC-123', 'status': 'ACTIVE'})
        self.assertRedirects(old, reverse('records_list') + '?q=ABC-123&status=ACTIVE')
        self.client.logout()
        self.assertEqual(self.client.get(reverse('records_list')).status_code, 302)

    def test_pending_preview_is_limited_ordered_and_excludes_answers(self):
        self.client.force_login(self.user)
        for index in range(2, 8):
            Letter.objects.create(full_number=f'CPC-{index:04}', correlative=index,
                direction='CPC_AAM', letter_date=date(2026, 1, index), created_by=self.user)
        answered = Letter.objects.get(full_number='CPC-0002')
        Letter.objects.create(full_number='AAM-0002', correlative=2, direction='AAM_CPC',
            letter_date=date(2026, 2, 1), response_to=answered, created_by=self.user)
        metrics = self.client.get(reverse('dashboard_data')).json()['metrics']
        self.assertEqual(metrics['pending_letters'], 6)
        self.assertEqual([item['number'] for item in metrics['pending_preview']],
                         ['CPC-0001', 'CPC-0003', 'CPC-0004', 'CPC-0005', 'CPC-0006'])
        home = self.client.get(reverse('dashboard'))
        self.assertContains(home, 'CPC-0001')
        self.assertNotContains(home, 'CPC-0002')
        self.assertContains(home, 'Ver todas las pendientes')

    def test_html_search_feedback_and_expedient_summary(self):
        self.client.force_login(self.user)
        dashboard = self.client.get(reverse('records_list'), {'q': 'no-existe'})
        self.assertContains(dashboard, 'No hay resultados para estos filtros.')
        self.assertContains(dashboard, '0 resultados')
        letters = self.client.get(reverse('letters'))
        self.assertContains(letters, 'Última carta pendiente')
        self.assertContains(letters, '1 expediente encontrado')
        self.assertContains(letters, '01/01/2026')
        self.assertContains(self.client.get(reverse('letters'), {'q': 'no-existe'}),
                            'No hay expedientes para estos filtros.')

    def payload(self, response):
        import json
        import re
        match = re.search(r'<script id="krys-data" type="application/json">(.*?)</script>', response.content.decode(), re.S)
        self.assertIsNotNone(match)
        return json.loads(match.group(1))

    def test_react_pages_and_form_validation(self):
        login = self.payload(self.client.get(reverse('login')))
        self.assertEqual(login['page'], 'login')
        self.assertFalse(login['authenticated'])
        failed = self.payload(self.client.post(reverse('login'), {'username': 'nobody', 'password': 'secret-to-hide'}))
        self.assertNotIn('secret-to-hide', str(failed))
        self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)
        for name in ('dashboard', 'records_list', 'letters', 'manual_record', 'upload_letters'):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.payload(response)['page'], name)
        upload = self.payload(self.client.get(reverse('upload_letters')))
        self.assertTrue(upload['form']['fields'][0]['attrs']['multiple'])
        response = self.client.post(reverse('manual_record'), {'cpc_full_number': 'invalid'})
        form = self.payload(response)['form']
        number = next(field for field in form['fields'] if field['name'] == 'cpc_full_number')
        self.assertEqual(number['value'], 'invalid')
        self.assertTrue(number['errors'])

    def test_manual_guidance_and_conditional_validation(self):
        self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)
        data = self.payload(self.client.get(reverse('manual_record')))
        fields = {field['name']: field for field in data['form']['fields']}
        self.assertTrue(fields['cpc_full_number']['required'])
        self.assertIn('subsanaciones', fields['predecessor_aam']['help'])
        response = self.client.post(reverse('manual_record'), {
            'cpc_full_number': 'PSR2-F2-CPC-AAM-GEN-GLB-CAR-0002',
            'cpc_date': '2026-01-01', 'reception_date': '2026-01-01',
            'equipment_type': 'Camioneta', 'equipment_code': 'PRUEBA-1',
            'result': 'OBSERVED', 'detail': '',
        })
        fields = {field['name']: field for field in self.payload(response)['form']['fields']}
        self.assertTrue(fields['aam_full_number']['errors'])
        self.assertTrue(fields['detail']['errors'])
        self.assertFalse(Equipment.objects.filter(code='PRUEBA-1').exists())

    def test_edit_and_delete_payloads(self):
        self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)
        presentation = Presentation.objects.get()
        for name, pk in [('edit_presentation', presentation.pk), ('edit_letter', presentation.cpc_letter_id), ('delete_letter', presentation.cpc_letter_id)]:
            response = self.client.get(reverse(name, args=[pk]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.payload(response)['page'], name)
        data = self.payload(self.client.get(reverse('letters')))
        self.assertEqual(data['expedients'][0][0]['presentations'][0]['code'], 'ABC-123')

    def test_preview_payload_excludes_internal_paths(self):
        self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)
        session = self.client.session
        session['upload_preview'] = {'batch_id': 'internal', 'documents': [{'correlative': 1, 'direction': 'CPC_AAM', 'path': '/private/file.pdf'}], 'rows': [], 'movement_rows': [], 'warnings': []}
        session.save()
        preview = self.payload(self.client.get(reverse('upload_letters')))['preview']
        self.assertEqual(preview['documents'], [{'correlative': 1, 'direction': 'CPC_AAM'}])
        self.assertNotIn('/private', str(preview))

    def test_profile_requires_login_and_shows_current_account(self):
        url = reverse('profile')
        self.assertEqual(self.client.get(url).status_code, 302)
        self.user.first_name = 'Ale'
        self.user.email = 'ale@example.test'
        self.user.save()
        self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.payload(response)['profile'], {'username': 'react-test', 'name': 'Ale', 'email': 'ale@example.test'})

    def test_client_page_responses_and_validation(self):
        self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)
        header = {'HTTP_X_KS_CLIENT': 'react'}
        response = self.client.get(reverse('letters'), **header)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(response.json()['expedients'][0][0]['presentations'][0]['code'], 'ABC-123')
        response = self.client.post(reverse('manual_record'), {'cpc_full_number': 'invalid'}, **header)
        field = next(f for f in response.json()['form']['fields'] if f['name'] == 'cpc_full_number')
        self.assertTrue(field['errors'])
        self.assertEqual(field['value'], 'invalid')
        self.assertIn('no-store', response['Cache-Control'])

    def test_client_routes_keep_authentication(self):
        response = self.client.get(reverse('profile'), HTTP_X_KS_CLIENT='react')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/ingresar/', response['Location'])

    def test_client_upload_preview_and_confirmation(self):
        import tempfile
        from pathlib import Path
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)
        samples = Path(os.environ.get('KRYS_TEST_SAMPLES_DIR', Path(__file__).resolve().parents[2]))
        names = ['PSR2-F2-CPC-AAM-GEN-GLB-CAR-0150.pdf', 'PSR2-F2-AAM-CPC-GEN-GLB-CAR-0118.pdf']
        files = [SimpleUploadedFile(name, (samples / name).read_bytes(), content_type='application/pdf') for name in names]
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=Path(media)):
            header = {'HTTP_X_KS_CLIENT': 'react'}
            response = self.client.post(reverse('upload_letters'), {'files': files}, **header)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json()['preview']['rows']), 2)
            self.assertEqual(Presentation.objects.count(), 1)
            response = self.client.post(reverse('confirm_upload'), {'reception_150': '2026-03-30'}, follow=True, **header)
            self.assertEqual(response.json()['page'], 'dashboard')
            self.assertEqual(Presentation.objects.count(), 3)
            self.assertTrue(response.json()['messages'])
