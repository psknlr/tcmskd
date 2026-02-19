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

# 2) 所有需要编译的包统一走 conda-forge 预编译版本
RUN micromamba install -y -n biomni \
      -c conda-forge \
      -c bioconda \
      openmm \
      scikit-misc \
      cython \
      biotraj \
      loompy \
      r-base \
      git \
      gcc \
      gxx \
      make && \
    micromamba clean -a -y

# 3) 升级 pip 并预装编译工具链
RUN micromamba run -n biomni \
    pip install -U pip setuptools wheel cython

# 4) 安装其余 pip 依赖（跳过已由 conda 满足的包）
RUN micromamba run -n biomni \
    pip install --no-cache-dir -r /tmp/requirements.pip.txt

ENTRYPOINT ["/bin/bash", "-lc"]
CMD ["eval \"$(micromamba shell hook --shell bash)\" && micromamba activate biomni && tail -f /dev/null"]
