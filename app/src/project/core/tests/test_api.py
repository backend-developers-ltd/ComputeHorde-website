import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from project.core.models import Job


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="testuser", password="testpass")


@pytest.fixture
def another_user(db):
    return User.objects.create_user(username="anotheruser", password="anotherpass")


@pytest.fixture
def job_docker(db, user, connected_validator, miner):
    return Job.objects.create(
        user=user,
        validator=connected_validator,
        miner=miner,
        docker_image="hello-world",
        args="my args",
        env={"MY_ENV": "my value"},
        use_gpu=True,
        input_url="http://example.com/input.zip",
    )


@pytest.fixture
def job_raw(db, user, connected_validator, miner):
    return Job.objects.create(
        user=user,
        validator=connected_validator,
        miner=miner,
        raw_script="print(1)",
        input_url="http://example.com/input.zip",
    )


@pytest.fixture
def another_user_job_raw(db, another_user, connected_validator, miner):
    return Job.objects.create(
        user=another_user,
        validator=connected_validator,
        miner=miner,
        raw_script="print(1)",
        input_url="http://example.com/input.zip",
    )


def check_docker_job(job_result):
    generated_fields = {
        "created_at",
        "last_update",
        "status",
        "output_download_url",
    }
    assert job_result["docker_image"] == "hello-world"
    assert job_result["raw_script"] == ""
    assert job_result["args"] == "my args"
    assert job_result["env"] == {"MY_ENV": "my value"}
    assert job_result["use_gpu"] is True
    assert job_result["input_url"] == "http://example.com/input.zip"
    assert set(job_result.keys()) & generated_fields == generated_fields


def check_raw_job(job_result):
    generated_fields = {
        "created_at",
        "last_update",
        "status",
        "output_download_url",
    }
    assert job_result["raw_script"] == "print(1)"
    assert job_result["docker_image"] == ""
    assert job_result["args"] == ""
    assert job_result["env"] == {}
    assert job_result["use_gpu"] is False
    assert job_result["input_url"] == "http://example.com/input.zip"
    assert set(job_result.keys()) & generated_fields == generated_fields


@pytest.mark.django_db(transaction=True)
def test_job_viewset_list(api_client, user, job_docker, job_raw):
    api_client.force_authenticate(user=user)
    response = api_client.get("/api/v1/jobs/")
    assert response.status_code == 200
    assert len(response.data["results"]) == 2

    docker_result = [job for job in response.data["results"] if job["uuid"] == str(job_docker.uuid)][0]
    raw_result = [job for job in response.data["results"] if job["uuid"] == str(job_raw.uuid)][0]
    check_docker_job(docker_result)
    check_raw_job(raw_result)


@pytest.mark.django_db(transaction=True)
def test_job_viewset_list_object_permissions(api_client, user, job_docker, job_raw, another_user_job_raw):
    api_client.force_authenticate(user=user)
    response = api_client.get("/api/v1/jobs/")
    assert response.status_code == 200
    assert len(response.data["results"]) == 2

    uuids = {job["uuid"] for job in response.data["results"]}
    assert uuids == {str(job_docker.uuid), str(job_raw.uuid)}


@pytest.mark.django_db(transaction=True)
def test_job_viewset_retrieve_docker(api_client, user, job_docker):
    api_client.force_authenticate(user=user)
    response = api_client.get(f"/api/v1/jobs/{job_docker.uuid}/")
    assert response.status_code == 200
    check_docker_job(response.data)


@pytest.mark.django_db(transaction=True)
def test_job_viewset_retrieve_raw(api_client, user, job_raw):
    api_client.force_authenticate(user=user)
    response = api_client.get(f"/api/v1/jobs/{job_raw.uuid}/")
    assert response.status_code == 200
    check_raw_job(response.data)


@pytest.mark.django_db(transaction=True)
def test_raw_job_viewset_create(api_client, user, connected_validator, miner):
    api_client.force_authenticate(user=user)
    data = {"raw_script": "print(1)", "input_url": "http://example.com/input.zip"}
    response = api_client.post("/api/v1/job-raw/", data)
    assert response.status_code == 201
    assert Job.objects.count() == 1
    job = Job.objects.first()
    assert job.raw_script == "print(1)"
    assert job.input_url == "http://example.com/input.zip"
    assert job.use_gpu is False
    assert job.user == user


@pytest.mark.django_db(transaction=True)
def test_docker_job_viewset_create(api_client, user, connected_validator, miner):
    api_client.force_authenticate(user=user)
    data = {"docker_image": "hello-world", "args": "my args", "env": {"MY_ENV": "my value"}, "use_gpu": True}
    response = api_client.post("/api/v1/job-docker/", data)
    assert response.status_code == 201
    assert Job.objects.count() == 1
    job = Job.objects.first()
    assert job.docker_image == "hello-world"
    assert job.args == "my args"
    assert job.env == {"MY_ENV": "my value"}
    assert job.use_gpu is True
    assert job.user == user
