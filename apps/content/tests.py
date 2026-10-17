from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.db import connection


class ContentAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Ensure SQLite unmanaged tables exist in test database
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS blog_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title VARCHAR(255) NOT NULL,
                    slug VARCHAR(255) UNIQUE NOT NULL,
                    excerpt TEXT NOT NULL,
                    content TEXT NOT NULL,
                    image_url VARCHAR(255),
                    author_name VARCHAR(100) DEFAULT 'Admin',
                    author_bio TEXT,
                    author_avatar VARCHAR(255),
                    category VARCHAR(100) DEFAULT 'Medical',
                    tags VARCHAR(255) DEFAULT 'Health,Care,Hospital',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    blog_id INTEGER NOT NULL,
                    parent_id INTEGER,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(100) NOT NULL,
                    website VARCHAR(255),
                    message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (blog_id) REFERENCES blog_posts (id)
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hospital_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key VARCHAR(50) UNIQUE NOT NULL,
                    title VARCHAR(100) NOT NULL,
                    number_value INTEGER DEFAULT 0,
                    suffix VARCHAR(20) DEFAULT '',
                    icon VARCHAR(100),
                    description TEXT
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS contact_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(100) NOT NULL,
                    subject VARCHAR(200) NOT NULL,
                    message TEXT NOT NULL,
                    is_read BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS newsletter_subscribers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Seed test data
            cursor.execute("""
                INSERT INTO blog_posts (title, slug, excerpt, content, category)
                VALUES ('Health Tips 2026', 'health-tips-2026', 'Tips for a healthy life', 'Full article content here', 'Wellness');
            """)
            cursor.execute("""
                INSERT INTO hospital_stats (key, title, number_value, suffix, icon)
                VALUES ('experience', 'Years of Experience', 30, '+', 'flaticon-stethoscope');
            """)

    def test_list_blogs(self):
        response = self.client.get('/api/v1/blogs/?limit=6&offset=0')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['slug'], 'health-tips-2026')

    def test_get_blog_detail(self):
        response = self.client.get('/api/v1/blogs/health-tips-2026/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Health Tips 2026')

    def test_get_recent_blogs(self):
        response = self.client.get('/api/v1/blogs/recent/?limit=3')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_get_blog_categories(self):
        response = self.client.get('/api/v1/blogs/categories/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(c['name'] == 'Wellness' for c in response.data))

    def test_post_comment(self):
        response = self.client.post('/api/v1/blogs/health-tips-2026/comments/', {
            'name': 'Alice Smith',
            'email': 'alice@example.com',
            'message': 'Great insights!'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Alice Smith')

    def test_get_stats(self):
        response = self.client.get('/api/v1/stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('stats', response.data)
        self.assertGreaterEqual(len(response.data['stats']), 1)

    def test_submit_contact_message(self):
        response = self.client.post('/api/v1/contact/', {
            'name': 'Bob Jones',
            'email': 'bob@example.com',
            'subject': 'Appointment Inquiry',
            'message': 'Can I book an appointment on Saturday?'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['subject'], 'Appointment Inquiry')

    def test_subscribe_newsletter(self):
        response = self.client.post('/api/v1/newsletter/subscribe/', {
            'email': 'subscriber@example.com'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['email'], 'subscriber@example.com')

