# FontInAss

实时将字体子集化后嵌入ass的小工具，用于在未安装对应字体的系统上正确显示字幕 

# 能做什么？

无需修改Emby服务器与客户端，实现使用Emby播放外挂ass字幕时，在没有安装字体的设备上正确显示字幕。

# 快速开始

## Docker 部署

```
docker run -d --name=fontinass --restart=unless-stopped \
  -p 8012:8012 \
  -e EMBY_SERVER_URL=http://[ip]:[port] \
  riderlty/fontinass:latest
```
设置EMBY_SERVER_URL为你的EMBY服务器的地址

在客户端上使用`http://[ip]:8012`访问容器代理的Emby

enjoy ~
 
## 配置说明

容器内部端口`8011`为字体处理服务，`8012`为nginx反向代理Emby

如有其他需求，可暴露`8011`端口

如果你有本地字体，将字体目录映射到`/fonts`下即可被自动识别

```
  -v /path/to/your/fonts1:/fonts/dir1 \
  -v /path/to/your/fonts2:/fonts/dir2 \
  -v /path/to/your/fonts3:/fonts/dir3 \
```

通过设置环境变量，可实现SRT转ASS，统一在不同设备上的播放效果
```
  -e SRT_2_ASS_FORMAT='Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding'
  -e SRT_2_ASS_STYLE='Default,楷体,20,&H03FFFFFF,&H00FFFFFF,&H00000000,&H02000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1'
```




# 原理说明

## 字体子集化

对字体文件进行处理，仅保留字幕文件用到了的字体，从而缩小字体体积

## 字体嵌入ass
使用UUEncode对子集化后的字体二进制文件进行编码，在ass内添加[Fonts]标签，将编码后字体嵌入字幕（不保证兼容性，部分播放器可能不支持）

## nginx

拦截/videos/(.*)/Subtitles请求，将内容发送到程序处理后，替换原本的内容返回给客户端

# 其他说明

自带的 [fontMap.json](https://github.com/RiderLty/fontInAss/blob/main/fontMap.json) 文件来自[超级字体整合包 XZ](https://vcb-s.com/archives/1114) , 通过cloudflare R2提供

程序会读取运行目录下`fonts`文件夹内的字体，创建本地字体数据库并优先调用本地字体
