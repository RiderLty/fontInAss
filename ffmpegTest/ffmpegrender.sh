# ffmpeg -i /mnt/storage/Projects/fontInAss/ffmpegTest/test.ass \
#        -vf "drawbox=color=black@1:x=0:y=0:width=1920:height=1080,subtitles=/mnt/storage/Projects/fontInAss/ffmpegTest/test.ass:fontsdir=/mnt/storage/Projects/fontInAss/fonts" \
#        -t 3 \
#        -vframes 1 \
#        output.png


# ffmpeg -i input.ass \
#        -f lavfi -i color=black:s=1920x1080 \
#        -filter_complex "[1:v][0:s]overlay=0:0" \
#        -ss 10 \
#        -vframes 1 \
#        output.png

# ffmpeg -f lavfi -i color=c:black@0:duration=1 -vf "ass=input.ass" -ss 00:00:03 -vframes 1 -s 1920x1080 output.png

# ffmpeg -y -f lavfi -i "color=c=black@0.0:s=1920x1080:r=50:d=00\\:00\\:30,format=rgba,subtitles=f=input.ass:alpha=1" -c:v png test.mov

ffmpeg -f lavfi -i color=#000000@0:s=1920x1080 -vf "subtitles=/mnt/storage/Projects/fontInAss/ffmpegTest/input.ass:fontsdir=/mnt/storage/Projects/fontInAss/ffmpegTest/fonts" -ss 3 -vframes 1 -vsync 0 -f image2pipe -vframes 1 -  > /dev/null 


# ffmpeg -f lavfi -i color=#000000@0:s=1920x1080 -vf "subtitles=/dev/stdin" -ss 3 -vframes 1 -vsync 0 -f image2pipe -vframes 1 - # 管道输入 输出