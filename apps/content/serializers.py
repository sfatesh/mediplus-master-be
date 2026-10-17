from rest_framework import serializers
from .models import BlogPost, Comment, HospitalStat, ContactMessage, NewsletterSubscriber


class CommentSerializer(serializers.ModelSerializer):
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['id', 'blog_id', 'parent_id', 'name', 'email', 'website', 'message', 'created_at', 'replies']
        read_only_fields = ['id', 'created_at', 'replies']

    def get_replies(self, obj):
        if obj.parent_id is None:
            replies = obj.replies.all()
            return CommentSerializer(replies, many=True).data
        return []


class BlogPostSerializer(serializers.ModelSerializer):
    comment_count = serializers.SerializerMethodField()

    class Meta:
        model = BlogPost
        fields = [
            'id', 'title', 'slug', 'excerpt', 'content', 'image_url',
            'author_name', 'author_bio', 'author_avatar',
            'category', 'tags', 'created_at', 'comment_count'
        ]

    def get_comment_count(self, obj):
        return obj.comments.count()


class BlogPostDetailSerializer(BlogPostSerializer):
    comments = serializers.SerializerMethodField()

    class Meta(BlogPostSerializer.Meta):
        fields = BlogPostSerializer.Meta.fields + ['comments']

    def get_comments(self, obj):
        top_comments = obj.comments.filter(parent__isnull=True)
        return CommentSerializer(top_comments, many=True).data


class HospitalStatSerializer(serializers.ModelSerializer):
    class Meta:
        model = HospitalStat
        fields = ['key', 'title', 'number_value', 'suffix', 'icon', 'description']


class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ['id', 'name', 'email', 'subject', 'message', 'is_read', 'created_at']
        read_only_fields = ['id', 'is_read', 'created_at']


class NewsletterSubscriberSerializer(serializers.ModelSerializer):
    message = serializers.CharField(default="Thank you for subscribing to Mediplus updates!", read_only=True)

    class Meta:
        model = NewsletterSubscriber
        fields = ['id', 'email', 'is_active', 'subscribed_at', 'message']
        read_only_fields = ['id', 'is_active', 'subscribed_at', 'message']

