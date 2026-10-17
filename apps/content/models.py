from django.db import models
from django.utils import timezone


class BlogPost(models.Model):
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    excerpt = models.TextField()
    content = models.TextField()
    image_url = models.CharField(max_length=255, blank=True, null=True)
    author_name = models.CharField(max_length=100, default='Admin')
    author_bio = models.TextField(blank=True, null=True)
    author_avatar = models.CharField(max_length=255, blank=True, null=True)
    category = models.CharField(max_length=100, default='Medical', db_index=True)
    tags = models.CharField(max_length=255, default='Health,Care,Hospital')
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = 'blog_posts'
        verbose_name = 'Blog Post'
        verbose_name_plural = 'Blog Posts'
        managed = False
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Comment(models.Model):
    id = models.BigAutoField(primary_key=True)
    blog = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='comments', db_column='blog_id')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies', db_column='parent_id')
    name = models.CharField(max_length=100)
    email = models.EmailField(max_length=100)
    website = models.CharField(max_length=255, blank=True, null=True)
    message = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'comments'
        verbose_name = 'Comment'
        verbose_name_plural = 'Comments'
        managed = False
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.name} on blog {self.blog_id}"


class HospitalStat(models.Model):
    id = models.BigAutoField(primary_key=True)
    key = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=100)
    number_value = models.IntegerField(default=0)
    suffix = models.CharField(max_length=20, blank=True, default='')
    icon = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'hospital_stats'
        verbose_name = 'Hospital Stat'
        verbose_name_plural = 'Hospital Stats'
        managed = False

    def __str__(self):
        return f"{self.title}: {self.number_value}{self.suffix}"


class ContactMessage(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(max_length=100)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'contact_messages'
        verbose_name = 'Contact Message'
        verbose_name_plural = 'Contact Messages'
        managed = False
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.subject} ({self.email})"


class NewsletterSubscriber(models.Model):
    id = models.BigAutoField(primary_key=True)
    email = models.EmailField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    subscribed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'newsletter_subscribers'
        verbose_name = 'Newsletter Subscriber'
        verbose_name_plural = 'Newsletter Subscribers'
        managed = False
        ordering = ['-subscribed_at']

    def __str__(self):
        return self.email

