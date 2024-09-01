docker stop test

docker rmi test && docker build /mnt/user/storage/Projects/fontInAss/ -t test

docker run  --name test --rm -p 9999:8012 -p 9998:8011  -e EMBY_SERVER_URL="http://192.168.3.3:7096"  test 