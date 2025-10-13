docker buildx build --platform linux/amd64,linux/arm64 -t xmayeur/wixgooglesheet . --push && \
ssh -p 5210 root@contabo 'docker pull xmayeur/wixgooglesheet && \
docker compose up -d wixgoogle'