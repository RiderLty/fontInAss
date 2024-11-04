docker rmi $(docker images -f "dangling=true" -q)

cd /mnt/user/storage/Projects/fontInAss/
docker stop test

docker build . -t test --build-arg NGINX=NO

docker run  --name test --rm -p 9999:8012 -p 9998:8011  -e EMBY_SERVER_URL="http://192.168.3.3:7096"  test 

docker run  --name test --rm -it -p 9999:8012 -p 9998:8011  -e EMBY_SERVER_URL="http://192.168.3.3:7096"  test /bin/bash

export EMBY_SERVER_URL="http://192.168.3.3:7096"
export SRT_2_ASS_FORMAT='Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding'
export SRT_2_ASS_STYLE='Style: Default,楷体,20,&H03FFFFFF,&H00FFFFFF,&H00000000,&H02000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1'
export DEV="true"