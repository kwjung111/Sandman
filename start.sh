#!/bin/bash
if [ "$#" -lt 2 ]; then
    echo "사용법: $0 <ACCESS_KEY> <SECRET_KEY>"
    exit 1
fi

docker run -d \
   --name ncp-manager \
   --restart unless-stopped \
   -p 8080:8000 \
   -e NCP_ACCESS_KEY="$1" \
   -e NCP_SECRET_KEY="$2" \
   -e NCP_API_URL="https://ncloud.apigw.gov-ntruss.com" \
   -e WORK_START_HOUR=8\
   -e WORK_START_MINUTE=25 \
   -e WORK_END_HOUR=17 \
   -e WORK_END_MINUTE=40 \
   -e INCLUDE_WEEKENDS=true \
   -e SERVER_NAME_FILTER="dev" \
   -e SERVER_NAME_EXCLUDE="prd,stg" \
   ncp-server-manager