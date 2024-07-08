docker build -t xmayeur/wixgooglesheet . --push && \
ssh pi@sushi 'docker pull xmayeur/wixgooglesheet && \
docker compose up -d wixgoogle'