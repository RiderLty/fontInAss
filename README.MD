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
  -v /etc/localFontMap.json:/localFontMap.json \
  riderlty/fontinass:latest
```
设置EMBY_SERVER_URL为你的EMBY服务器的地址

映射/localFontMap.json到你的数据保存位置，避免每次更新容器重复扫描本地字体

在客户端上使用`http://[ip]:8012`访问容器代理的Emby

enjoy ~

## Unraid部署

下载模版
``` sh
curl -o /boot/config/plugins/dockerMan/templates-user/my-fontinass.xml  https://raw.githubusercontent.com/RiderLty/fontInAss/refs/heads/main/my-fontinass.xml
```
Docker > 添加容器 > 选择一个模版 > fontinass

移除你不需要的配置项

应用
## 手动运行

安装依赖
```
pip install -r ./requirements.txt
```
修改main.py，中，EMBY_SERVER_URL为你的emby服务器地址，例如：
```
EMBY_SERVER_URL = "http://192.168.3.3:7096"
```
添加nginx反向代理
```
server {
    listen 8012; #新的Emby访问端口
    
    location ~ /(socket|embywebsocket) {
        proxy_pass $EMBY_SERVER_URL;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Protocol $scheme;
        proxy_set_header X-Forwarded-Host $http_host;
    }

    location ~* /videos/(.*)/Subtitles {
        #修改为你的fontinass服务器地址
        proxy_pass http://127.0.0.1:8011;
    }

    location / {
        #修改为你的EMBY服务器地址
        proxy_pass $EMBY_SERVER_URL;
    }
}
```

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
  -e SRT_2_ASS_STYLE='Style: Default,楷体,20,&H03FFFFFF,&H00FFFFFF,&H00000000,&H02000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1'
```

程序默认字体与字幕缓存大小为32，可修改CACHE_SIZE来自定义
```
-e CACHE_SIZE=1024
```

支持[HDR适配](https://github.com/yyymeow/ssaHdrify)，避免亮度过高

通过HDR来设置字幕亮度峰值, 例如1000nit
```
-e HDR=1000
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
