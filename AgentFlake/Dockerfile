FROM maven:3.8.6-openjdk-8

WORKDIR /app

RUN apt-get update && \
    apt-get install -y autoconf automake libtool curl make g++ unzip python3 python3-pip && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    rm -rf /var/lib/apt/lists/*

RUN apt-get update && \
    apt-get install -y xmlstarlet && \
    rm -rf /var/lib/apt/lists/*

RUN pip3 install beautifulsoup4 lxml

ENV MAVEN_OPTS="-Dmaven.repo.local=/root/.m2/repository"
CMD ["/bin/bash"]
