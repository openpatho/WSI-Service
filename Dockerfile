FROM registry.gitlab.com/empaia/integration/ci-docker-images/test-runner:0.2.8@sha256:0c20dd487c2bb040fd78991bf54f396cb1fd9ab314a7a55bee0ad4909748797d AS wsi_service_build

# EDIT to set version of OpenSlide
ENV OPENSLIDE_VERSION=3390d5a

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
  && apt-get install --no-install-recommends -y \
  python3-openslide

RUN mkdir /openslide_deps

RUN curl -o /usr/lib/x86_64-linux-gnu/libopenslide.so.0 \
  https://gitlab.com/api/v4/projects/36668960/packages/generic/libopenslide.so.0/$OPENSLIDE_VERSION/libopenslide.so.0

RUN cp /usr/lib/x86_64-linux-gnu/libopenslide.so.0 /openslide_deps
RUN ldd /usr/lib/x86_64-linux-gnu/libopenslide.so.0 \
  | grep "=> /" | awk '{print $3}' | xargs -I '{}' cp -v '{}' /openslide_deps

COPY . /wsi-service

WORKDIR /wsi-service
RUN poetry build && poetry export -f requirements.txt > requirements.txt

WORKDIR /wsi-service/wsi_service_base_plugins/openslide
RUN poetry build && poetry export -f requirements.txt > requirements.txt

WORKDIR /wsi-service/wsi_service_base_plugins/pil
RUN poetry build && poetry export -f requirements.txt > requirements.txt

WORKDIR /wsi-service/wsi_service_base_plugins/tifffile
RUN poetry build && poetry export -f requirements.txt > requirements.txt

WORKDIR /wsi-service/wsi_service_base_plugins/tiffslide
RUN poetry build && poetry export -f requirements.txt > requirements.txt

WORKDIR /wsi-service/wsi_service_base_plugins/wsidicom
RUN poetry build && poetry export -f requirements.txt > requirements.txt


FROM wsi_service_build AS wsi_service_dev

WORKDIR /wsi-service
RUN poetry install


FROM ubuntu:22.04@sha256:bcc511d82482900604524a8e8d64bf4c53b2461868dac55f4d04d660e61983cb AS wsi_service_intermediate

RUN apt-get update \
  && apt-get install --no-install-recommends -y build-essential python3-pip curl python3-packaging python3-dev curl ca-certificates\
  && rm -rf /var/lib/apt/lists/*

RUN mkdir /artifacts

######## uv installation ##########

# Download the latest installer
RUN pip install uv

####### continue docker ###########



COPY --from=wsi_service_build /wsi-service/requirements.txt /artifacts

COPY wsi_service/utils/cloudwrappers/requirements.txt /artifacts/cw_requirements.txt

COPY --from=wsi_service_build /wsi-service/wsi_service_base_plugins/openslide/requirements.txt /artifacts/requirements_openslide.txt

COPY --from=wsi_service_build /wsi-service/wsi_service_base_plugins/pil/requirements.txt /artifacts/requirements_pil.txt

COPY --from=wsi_service_build /wsi-service/wsi_service_base_plugins/tifffile/requirements.txt /artifacts/requirements_tiffile.txt

COPY --from=wsi_service_build /wsi-service/wsi_service_base_plugins/tiffslide/requirements.txt /artifacts/requirements_tiffslide.txt

COPY --from=wsi_service_build /wsi-service/wsi_service_base_plugins/wsidicom/requirements.txt /artifacts/requirements_wsidicom.txt

RUN uv pip install -r /artifacts/requirements.txt -r /artifacts/cw_requirements.txt -r /artifacts/requirements_openslide.txt -r /artifacts/requirements_pil.txt -r /artifacts/requirements_tiffile.txt -r /artifacts/requirements_tiffslide.txt -r /artifacts/requirements_wsidicom.txt --system

COPY --from=wsi_service_build /wsi-service/dist/ /wsi-service/dist/
COPY --from=wsi_service_build /wsi-service/wsi_service_base_plugins/openslide/dist/ /wsi-service/dist/
COPY --from=wsi_service_build /wsi-service/wsi_service_base_plugins/pil/dist/ /wsi-service/dist/
COPY --from=wsi_service_build /wsi-service/wsi_service_base_plugins/tifffile/dist/ /wsi-service/dist/
COPY --from=wsi_service_build /wsi-service/wsi_service_base_plugins/tiffslide/dist/ /wsi-service/dist/
COPY --from=wsi_service_build /wsi-service/wsi_service_base_plugins/wsidicom/dist/ /wsi-service/dist/

RUN uv pip install /wsi-service/dist/*.whl --system


RUN mkdir /data


FROM ubuntu:22.04@sha256:bcc511d82482900604524a8e8d64bf4c53b2461868dac55f4d04d660e61983cb AS wsi_service_production

RUN apt-get update \
  && apt-get install --no-install-recommends -y python3 python3-pip curl python3-packaging \
  && rm -rf /var/lib/apt/lists/*

COPY --from=wsi_service_build /openslide_deps/* /usr/lib/x86_64-linux-gnu/

COPY --from=wsi_service_intermediate /usr/local/lib/python3.10/dist-packages/ /usr/local/lib/python3.10/dist-packages/
COPY --from=wsi_service_intermediate /data /data


ENV WEB_CONCURRENCY=8

EXPOSE 8080/tcp

WORKDIR /usr/local/lib/python3.10/dist-packages/wsi_service

COPY public_environment_settings .env
COPY wsi_service/api/v3/integrations/.env cog.env

CMD ["python3", "-m", "uvicorn", "wsi_service.app:app", "--host", "0.0.0.0", "--port", "8080", "--loop=uvloop", "--http=httptools"]
