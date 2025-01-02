#!/bin/bash
#run wireshark in linux
#wireshark
docker stop machine1 machine2
docker rm machine1 machine2
docker rmi vsomeip
docker network rm vsomeip 
docker build --no-cache -t vsomeip -f Dockerfile .
docker network create --subnet=172.18.0.0/16 vsomeip
docker run -d --name machine1 -v "$(pwd):/opt/vsomeip" -w /opt/vsomeip --net vsomeip --ip 172.18.0.2 -it vsomeip
docker run -d --name machine2 -v "$(pwd):/opt/vsomeip" -w /opt/vsomeip --net vsomeip --ip 172.18.0.3 -it vsomeip
#build vsomeip
docker exec machine1 /bin/bash -c "cd /opt/vsomeip/ && rm -rf build && mkdir build && cd build && cmake .. && make"
#install vsomeip
docker exec machine1 /bin/bash -c "cd /opt/vsomeip/ && make install"
docker exec machine2 /bin/bash -c "cd /opt/vsomeip/ && make install"
#build hello_world
docker exec machine1 /bin/bash -c "cd /opt/vsomeip/examples/hello_world && rm -rf build && mkdir build && cd build && cmake .. && make"
#run hello_world
docker exec -d machine1 /bin/bash -c "cd /opt/vsomeip/examples/hello_world/build && ldconfig && VSOMEIP_CONFIGURATION=$(realpath ../helloworld-local-client.json) VSOMEIP_APPLICATION_NAME=hello_world_client ./hello_world_client"
docker exec -d machine2 /bin/bash -c "cd /opt/vsomeip/examples/hello_world/build && ldconfig && VSOMEIP_CONFIGURATION=$(realpath ../helloworld-local-service.json) VSOMEIP_APPLICATION_NAME=hello_world_service ./hello_world_service"
