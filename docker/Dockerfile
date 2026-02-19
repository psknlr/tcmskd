FROM mambaorg/micromamba:1.5.10

ARG MAMBA_DOCKERFILE_ACTIVATE=1
ENV CONDA_PREFIX=/opt/conda
ENV PATH=${CONDA_PREFIX}/bin:$PATH

WORKDIR /workspace

COPY env_spec/environment.base.yml /tmp/environment.base.yml
COPY env_spec/requirements.pip.txt /tmp/requirements.pip.txt

# 1) 重建 conda 环境
RUN micromamba create -y -n biomni \
      -c bioconda \
      -c conda-forge \
      -f /tmp/environment.base.yml && \
    micromamba clean -a -y

# 2) 用 micromamba run 替代 activate 装 pip 依赖
RUN micromamba run -n biomni \
    python -m pip install -U pip setuptools wheel && \
    micromamba run -n biomni \
    pip install -r /tmp/requirements.pip.txt

# 3) 确保 R 可用
RUN micromamba install -y -n biomni \
      -c conda-forge \
      r-base && \
    micromamba clean -a -y

ENTRYPOINT ["/bin/bash", "-lc"]
CMD ["eval \"$(micromamba shell hook --shell bash)\" && micromamba activate biomni && tail -f /dev/null"]
