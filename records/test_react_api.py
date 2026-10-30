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
        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard_data'), {'q': 'ABC-123'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['metrics']['total'], 1)
        self.assertEqual(data['records'][0]['equipment'], 'ABC-123')
        self.assertEqual(data['records'][0]['resultLabel'], 'Pendiente')
        self.assertEqual(self.client.get(reverse('dashboard_data'), {'q': 'inexistente'}).json()['records'], [])

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
        self.client.force_login(self.user)
        for name in ('dashboard', 'letters', 'manual_record', 'upload_letters'):
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

    def test_edit_and_delete_payloads(self):
        self.client.force_login(self.user)
        presentation = Presentation.objects.get()
        for name, pk in [('edit_presentation', presentation.pk), ('edit_letter', presentation.cpc_letter_id), ('delete_letter', presentation.cpc_letter_id)]:
            response = self.client.get(reverse(name, args=[pk]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.payload(response)['page'], name)
        data = self.payload(self.client.get(reverse('letters')))
        self.assertEqual(data['expedients'][0][0]['presentations'][0]['code'], 'ABC-123')

    def test_preview_payload_excludes_internal_paths(self):
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
        self.client.force_login(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.payload(response)['profile'], {'username': 'react-test', 'name': 'Ale', 'email': 'ale@example.test'})

    def test_client_page_responses_and_validation(self):
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
        self.client.force_login(self.user)
        samples = Path('/home/aleu/Documentos/proyecto-krys')
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
