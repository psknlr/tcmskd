FROM mambaorg/micromamba:1.5.10

ARG MAMBA_DOCKERFILE_ACTIVATE=1
ENV CONDA_PREFIX=/opt/conda
ENV PATH=${CONDA_PREFIX}/bin:$PATH

WORKDIR /workspace

COPY env_spec/environment.base.yml /tmp/environment.base.yml
COPY env_spec/requirements.pip.txt /tmp/requirements.pip.txt

# 1) 重建 conda 环境 + 需要编译的包走 conda + 装 git（解决 meson version_please.py 问题）
RUN micromamba create -y -n biomni \
      -c bioconda \
      -c conda-forge \
      -f /tmp/environment.base.yml && \
    micromamba install -y -n biomni \
      -c conda-forge \
      openmm \
      r-base \
      git && \
    micromamba clean -a -y

# 2) 先单独安装 scikit-misc（设置假版本号绕过 git describe）
RUN SETUPTOOLS_SCM_PRETEND_VERSION=0.5.2 \
    micromamba run -n biomni \
    pip install --no-cache-dir scikit-misc==0.5.2

# 3) 安装其余 pip 依赖
RUN micromamba run -n biomni \
    python -m pip install -U pip setuptools wheel && \
    micromamba run -n biomni \
    pip install --no-cache-dir -r /tmp/requirements.pip.txt

ENTRYPOINT ["/bin/bash", "-lc"]
CMD ["eval \"$(micromamba shell hook --shell bash)\" && micromamba activate biomni && tail -f /dev/null"]
