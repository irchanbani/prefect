from collections import OrderedDict
import marshmallow
import prefect
from marshmallow_oneofschema import OneOfSchema
from marshmallow import fields, pre_dump, post_load, pre_load, post_dump
from prefect.utilities.serialization import (
    VersionedSchema,
    version,
    to_qualified_name,
    from_qualified_name,
)
from prefect.serialization.schedule import ScheduleSchema
from prefect.utilities.serialization import JSONField


class FunctionReference(fields.Field):
    """
    Field that stores a reference to a function as a string and reloads it when
    deserialized.
    """

    def _serialize(self, value, attr, obj, **kwargs):
        return to_qualified_name(value)

    def _deserialize(self, value, attr, data, **kwargs):
        return from_qualified_name(value)


class TaskMethodsMixin:
    def dump_task_id(self, obj):
        """
        Helper for serializing task IDs that may have been placed in the context dict

        Args:
            - obj (Task): the object being serialized

        Returns:
            - str: the object ID
        """
        if isinstance(obj, prefect.core.Task) and "task_ids" in self.context:
            return self.context["task_ids"].get(obj, None)

    def load_task_id(self, data):
        """
        Helper for loading task IDs (required because `id` is a Method field)

        Args:
            - data (str): the id of the object

        Returns:
            - str: the object ID
        """
        return data

    def get_attribute(self, obj, key, default):
        """
        By default, Marshmallow attempts to index an object, then get its attributes.
        Indexing a Task results in a new IndexTask, so for tasks we use getattr(). Otherwise
        we use the default method.
        """
        if isinstance(obj, prefect.Task):
            return getattr(obj, key, default)
        else:
            return super().get_attribute(obj, key, default)

    @post_load
    def create_object(self, data):
        """
        Sometimes we deserialize tasks and edges simultaneously (for example, when a
        Flow is being deserialized), in which case we check IDs to see if we already
        deserialized a matching task. In that case, we reload the task from a shared
        cache.
        """
        task_id = data.get("id", None)
        if task_id not in self.context.setdefault("task_cache", {}) or task_id is None:
            task = super().create_object(data)
            task._id = task_id
            task._type = data.get("type", None)
            self.context["task_cache"][task_id] = task

        return self.context["task_cache"][task_id]


@version("0.3.3")
class TaskSchema(TaskMethodsMixin, VersionedSchema):
    class Meta:
        object_class = lambda: prefect.core.Task
        object_class_exclude = ["id", "type"]

    id = fields.Method("dump_task_id", "load_task_id", allow_none=True)
    type = fields.Function(lambda task: to_qualified_name(type(task)), lambda x: x)
    name = fields.String(allow_none=True)
    slug = fields.String(allow_none=True)
    description = fields.String(allow_none=True)
    tags = fields.List(fields.String())
    max_retries = fields.Integer(allow_none=True)
    retry_delay = fields.TimeDelta(allow_none=True)
    timeout = fields.TimeDelta(allow_none=True)
    trigger = FunctionReference(allow_none=True)
    skip_on_upstream_skip = fields.Boolean(allow_none=True)
    cache_for = fields.TimeDelta(allow_none=True)
    cache_validator = FunctionReference(allow_none=True)


@version("0.3.3")
class ParameterSchema(TaskMethodsMixin, VersionedSchema):
    class Meta:
        object_class = lambda: prefect.core.task.Parameter
        object_class_exclude = ["id", "type"]

    id = fields.Method("dump_task_id", "load_task_id", allow_none=True)
    type = fields.Function(lambda task: to_qualified_name(type(task)), lambda x: x)
    name = fields.String(allow_none=True)
    default = JSONField(allow_none=True)
    required = fields.Boolean(allow_none=True)
    description = fields.String(allow_none=True)
    tags = fields.List(fields.String())
