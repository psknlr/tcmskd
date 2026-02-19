FROM mambaorg/micromamba:1.5.10

ARG MAMBA_DOCKERFILE_ACTIVATE=1
ENV CONDA_PREFIX=/opt/conda
ENV PATH=${CONDA_PREFIX}/bin:$PATH

WORKDIR /workspace

COPY env_spec/environment.base.yml /tmp/environment.base.yml
COPY env_spec/requirements.pip.txt /tmp/requirements.pip.txt

# 1) 重建 conda 环境（含生信工具 + 需要编译的包统一走 conda）
RUN micromamba create -y -n biomni \
      -c bioconda \
      -c conda-forge \
      -f /tmp/environment.base.yml && \
    micromamba install -y -n biomni \
      -c conda-forge \
      openmm \
      scikit-misc \
      r-base && \
    micromamba clean -a -y

# 2) 装 pip 依赖（已过滤掉无 arm64 wheel 的包）
RUN micromamba run -n biomni \
    python -m pip install -U pip setuptools wheel && \
    micromamba run -n biomni \
    pip install --no-cache-dir -r /tmp/requirements.pip.txt

ENTRYPOINT ["/bin/bash", "-lc"]
CMD ["eval \"$(micromamba shell hook --shell bash)\" && micromamba activate biomni && tail -f /dev/null"]
