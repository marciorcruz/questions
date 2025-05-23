from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from django.apps import apps
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework.serializers import ModelSerializer
import json

# Serialização segura com fallback
def serialize_instance(instance):
    try:
        class AutoSerializer(ModelSerializer):
            class Meta:
                model = instance.__class__
                fields = '__all__'
        serializer = AutoSerializer(instance)
        return serializer.data
    except Exception as e:
        raise ValueError(f"[Serialization Error] {e}")

# Simula envio para Pub/Sub (print no terminal)
def publish_event(action, model_name, instance_data):
    try:
        event = {
            "action": action,
            "model": model_name,
            "data": instance_data,
        }
        print("[PUBSUB DEBUG]", json.dumps(event, cls=DjangoJSONEncoder, indent=2))
    except Exception as e:
        raise RuntimeError(f"[Publish Error] {e}")

# Ignora modelos internos do Django
def is_trackable(model):
    return hasattr(model, '_meta') and not model._meta.abstract and model._meta.app_label not in ['admin', 'contenttypes', 'sessions']

@receiver(post_save)
def on_any_model_save(sender, instance, created, **kwargs):
    if not is_trackable(sender):
        return

    action = 'insert' if created else 'update'

    try:
        data = serialize_instance(instance)
    except Exception as e:
        print(f"[ERROR] Falha na serialização de {sender.__name__}: {e}")
        return

    def publish_after_commit():
        try:
            publish_event(action, sender.__name__, data)
        except Exception as e:
            print(f"[ERROR] Falha ao publicar {sender.__name__}: {e}")

    transaction.on_commit(publish_after_commit)


@receiver(post_delete)
def on_any_model_delete(sender, instance, **kwargs):
    if not is_trackable(sender):
        return

    try:
        data = serialize_instance(instance)
    except Exception as e:
        print(f"[ERROR] Falha na serialização de {sender.__name__}: {e}")
        return

    
    def publish_after_commit():
        try:
            publish_event("delete", sender.__name__, data)
        except Exception as e:
            print(f"[ERROR] Falha ao publicar {sender.__name__}: {e}")

    transaction.on_commit(publish_after_commit)
