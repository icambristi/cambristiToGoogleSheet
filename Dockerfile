FROM python:3.11-alpine

LABEL author="Xavier Mayeur"
LABEL version="1.0"
LABEL creation_date="2024-06-22"
LABEL maintainer="xavier@mayeur.be"

ENV PROJ_DIR="/app"
ENV LOG_FILE="${PROJ_DIR}/app.log"
ENV CRON_SPEC="0 5 * * *"

WORKDIR ${PROJ_DIR}
RUN mkdir -p ${PROJ_DIR} /root/.config/.vault /root/.ssl

COPY writeGoogleSheet.py  ${PROJ_DIR}
COPY config.yml  ${PROJ_DIR}
COPY requirements.txt ${PROJ_DIR}
# COPY crontab ${PROJ_DIR}

RUN pip install --upgrade pip
RUN pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
RUN echo "${CRON_SPEC} python ${PROJ_DIR}/writeGoogleSheet.py >> ${LOG_FILE} 2>&1" > ${PROJ_DIR}/crontab

RUN touch ${LOG_FILE} # Needed for the tail
RUN crontab ${PROJ_DIR}/crontab
RUN crontab -l
CMD crond  && tail -f ${LOG_FILE}
