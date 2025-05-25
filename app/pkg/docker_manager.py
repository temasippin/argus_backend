import docker
from fastapi import HTTPException, status
from app.config import settings


class DockerManager:
    def __init__(self):
        try:
            self.client = docker.from_env()
        except docker.errors.DockerException as e:
            # Это произойдет, если Docker недоступен (например, не запущен сервис или сокет не смонтирован)
            # В идеале, здесь нужно логирование, а не просто print
            print(f"Could not connect to Docker daemon: {e}")
            self.client = None  # Установка в None, чтобы можно было проверить в методах

    async def _get_container(self, container_name: str):
        if not self.client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Docker service is not available to the backend."
            )
        try:
            return self.client.containers.get(container_name)
        except docker.errors.NotFound:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Container '{container_name}' not found."
            )
        except docker.errors.APIError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Docker API error: {e}"
            )

    async def start_vpn_container(self):
        container_name = settings.openvpn.container_name  # Получаем из env
        container = await self._get_container(container_name)
        if container.status != 'running':
            try:
                container.start()
                # Дадим время контейнеру запуститься и OpenVPN подключиться
                # В реальном приложении может потребоваться более сложная проверка статуса VPN
                # await asyncio.sleep(5) # Пример задержки, если нужно
                return {"message": f"Container '{container_name}' started successfully."}
            except docker.errors.APIError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to start container '{container_name}': {e}"
                )
        return {"message": f"Container '{container_name}' is already running."}

    async def stop_vpn_container(self):
        container_name = settings.openvpn.container_name
        container = await self._get_container(container_name)
        if container.status == 'running':
            try:
                container.stop(timeout=5)  # Даем 5 секунд на остановку
                return {"message": f"Container '{container_name}' stopped successfully."}
            except docker.errors.APIError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to stop container '{container_name}': {e}"
                )
        return {"message": f"Container '{container_name}' is not running."}

    async def get_vpn_container_status(self):
        if not self.client:  # Если Docker недоступен
            return "Docker N/A"
        container_name = settings.openvpn.container_name
        try:
            container = self.client.containers.get(container_name)
            return container.status
        except docker.errors.NotFound:
            return "not_found"
        except docker.errors.APIError:
            return "api_error"
