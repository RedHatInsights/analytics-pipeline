from buildkite/puppeteer

RUN apt -y update && apt -y install curl && apt -y clean
RUN useradd runner
RUN rm -rf /home/runner
RUN cp -Rp /home/node /home/runner
RUN chown -R runner:runner /home/runner
