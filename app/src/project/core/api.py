import django_filters
from django.core.exceptions import ObjectDoesNotExist
from django_filters import fields
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, routers, serializers, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from .models import Job


class DefaultModelPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 256


class JobSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Job
        fields = (
            "uuid",
            "created_at",
            "last_update",
            "status",
            "docker_image",
            "raw_script",
            "args",
            "env",
            "use_gpu",
            "input_url",
            "output_download_url",
            "tag",
            "stdout",
        )
        read_only_fields = (
            "created_at",
            "output_download_url",
        )

    status = serializers.SerializerMethodField()
    last_update = serializers.SerializerMethodField()
    stdout = serializers.SerializerMethodField()

    def get_status(self, obj):
        return obj.status.get_status_display()

    def get_stdout(self, obj):
        meta = obj.status.meta
        if meta and meta.miner_response:
            return meta.miner_response.docker_process_stdout
        return ""

    def get_last_update(self, obj):
        return obj.status.created_at


class RawJobSerializer(JobSerializer):
    class Meta:
        model = Job
        fields = JobSerializer.Meta.fields
        read_only_fields = tuple(set(JobSerializer.Meta.fields) - {"raw_script", "input_url", "tag"})


class DockerJobSerializer(JobSerializer):
    class Meta:
        model = Job
        fields = JobSerializer.Meta.fields
        read_only_fields = tuple(
            set(JobSerializer.Meta.fields) - {"docker_image", "args", "env", "use_gpu", "input_url", "tag"}
        )


class BaseCreateJobViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = Job.objects.with_statuses()

    def perform_create(self, serializer):
        try:
            serializer.save(user=self.request.user)
        except ObjectDoesNotExist as exc:
            model_name = exc.__class__.__qualname__.partition(".")[0]
            raise ValidationError(f"Could not select {model_name}")


class NonValidatingMultipleChoiceField(fields.MultipleChoiceField):
    def validate(self, value):
        pass


class NonValidatingMultipleChoiceFilter(django_filters.MultipleChoiceFilter):
    field_class = NonValidatingMultipleChoiceField


class JobViewSetFilter(django_filters.FilterSet):
    uuid = NonValidatingMultipleChoiceFilter(field_name="uuid")

    class Meta:
        model = Job
        fields = ["tag", "uuid"]


class JobViewSet(mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Job.objects.with_statuses()
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = DefaultModelPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = JobViewSetFilter

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)


class RawJobViewset(BaseCreateJobViewSet):
    serializer_class = RawJobSerializer


class DockerJobViewset(BaseCreateJobViewSet):
    serializer_class = DockerJobSerializer


class APIRootView(routers.DefaultRouter.APIRootView):
    description = "api-root"


class APIRouter(routers.DefaultRouter):
    APIRootView = APIRootView


router = APIRouter()
router.register(r"jobs", JobViewSet)
router.register(r"job-docker", DockerJobViewset, basename="job_docker")
router.register(r"job-raw", RawJobViewset, basename="job_raw")
