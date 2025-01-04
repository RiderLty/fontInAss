docker rmi $(docker images -f "dangling=true" -q)

cd /mnt/user/storage/Projects/fontInAss/
docker stop test

docker build . -f DockerfileBuild -t test-builder --rm

docker run -it --rm test-builder /bin/bash

# ========================================================

docker build . -t test --build-arg NGINX=NO --build-arg BUILDER=test-builder

docker run --rm -p 9999:8012 -p 9998:8011 -e EMBY_SERVER_URL="http://192.168.3.3:7096" test

docker run --rm -it -p 9999:8012 -p 9998:8011 -e EMBY_SERVER_URL="http://192.168.3.3:7096" test /bin/bash

export EMBY_SERVER_URL="http://192.168.3.3:7096"
export SRT_2_ASS_FORMAT='Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding'
export SRT_2_ASS_STYLE='Style: Default,楷体,20,&H03FFFFFF,&H00FFFFFF,&H00000000,&H02000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1'
export DEV="true"




docker run \
  -d \
  --name='fontinass' \
  --net='bridge' \
  -e TZ="Asia/Shanghai" \
  -e HOST_OS="Unraid" \
  -e HOST_HOSTNAME="NAS" \
  -e HOST_CONTAINERNAME="fontinass" \
  -e 'EMBY_SERVER_URL'='http://192.168.3.3:7096' \
  -e 'SUB_CACHE_SIZE'='1024' \
  -e 'SUB_CACHE_TTL'='60' \
  -e 'FONT_CACHE_SIZE'='1024' \
  -e 'FONT_CACHE_TTL'='-1' \
  -e 'HDR'='-1' \
  -e 'LOG_LEVEL'='DEBUG' \
  -e 'SRT_2_ASS_FORMAT'='Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding' \
  -e 'SRT_2_ASS_STYLE'='Style: Default,楷体,20,&H03FFFFFF,&H00FFFFFF,&H00000000,&H02000000,-1,0,0,0,100,100,0,0,1,1,0,2,10,10,10,1' \
  -l net.unraid.docker.managed=dockerman \
  -l net.unraid.docker.webui='http://[IP]:[PORT:8097]/' \
  -l net.unraid.docker.icon='https://www.foundertype.com/favicon.ico' \
  -p '8097:8012/tcp' \
  -p '8011:8011/tcp' \
  -v '/mnt/user/storage/Fonts/':'/fonts':'rw' \
  -v '/mnt/user/appdata/fontinass':'/data':'rw' \
  'riderlty/fontinass:noproxy'


curl -X POST --data-binary @'/mnt/storage/Projects/fontInAss/test/[DMG] 冴えない彼女の育てかた♭ [S02E02]「本気で本当な分岐点」 [BDRip][HEVC_FLAC][1080P_Ma10P](0C37FCAB).chs.ass' http://localhost:8011/fontinass/process_bytes > test.ass