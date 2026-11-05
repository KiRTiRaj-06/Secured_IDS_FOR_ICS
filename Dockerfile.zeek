FROM zeek/zeek:lts

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && zkg refresh \
    && zkg install --force icsnpp-dnp3
