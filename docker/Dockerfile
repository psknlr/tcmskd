# syntax=docker/dockerfile:1
FROM mambaorg/micromamba:1.5.10

ARG MAMBA_DOCKERFILE_ACTIVATE=1
ENV CONDA_PREFIX=/opt/conda
ENV PATH=${CONDA_PREFIX}/bin:$PATH

WORKDIR /workspace

# 拷贝环境定义
COPY env_spec/environment.base.yml /tmp/environment.base.yml
COPY env_spec/requirements.pip.txt /tmp/requirements.pip.txt

# 1) 重建 conda 环境
RUN micromamba create -y -n biomni \
      -c conda-forge \
      -f /tmp/environment.base.yml && \
    micromamba clean -a -y

# 2) 装 pip 依赖
RUN /bin/bash -lc "\
    micromamba activate biomni && \
    python -m pip install -U pip setuptools wheel && \
    pip install -r /tmp/requirements.pip.txt"

# 3) 确保 R 可用
RUN /bin/bash -lc "\
    micromamba activate biomni && \
    conda install -y -c conda-forge r-base && \
    conda clean -a -y"

# 修正：ENTRYPOINT + CMD 正确写法
ENTRYPOINT ["/bin/bash", "-lc"]
CMD ["micromamba activate biomni && tail -f /dev/null"]
