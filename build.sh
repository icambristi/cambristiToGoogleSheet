docker system prune -a --volumes
docker buildx build --platform linux/amd64,linux/arm64 -t xmayeur/wixgooglesheet . --push && \
ssh -p 5210 contabo 'sudo docker pull xmayeur/wixgooglesheet && \
sudo docker compose -f /root/docker-compose.yml up -d wixgoogle'