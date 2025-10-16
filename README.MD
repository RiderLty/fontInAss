# FontInAss

1、实时将字体子集化后嵌入ass的小工具，用于在未安装对应字体的系统上正确显示字幕  
2、批量字幕字体子集化嵌入后保存于本地。  

# 能做什么？

无需修改Emby/Jellyfin服务器与客户端，实现使用播放外挂ass/srt字幕时，在没有安装字体的设备上正确显示字幕。


![流程图](http://s3.rd5isto.org/img?id=c8afb503157c4f3fb124c5d38f4c30ec)


| 原效果                        | 子集化嵌入字体后                        |
|----------------------------|---------------------------------|
| ![原效果](image/example_origin.png) | ![子集化嵌入字体后](image/example_subset.png) |

# 快速开始

## Docker 部署

```
docker run -d --name=fontinass --restart=unless-stopped \
  -p 8011:8011 \
  -p 8012:8012 \
  -e EMBY_SERVER_URL=http://[ip]:[port] \
  -v /yourDir/fontinass/data:/data \
  -v /yourDir/fontinass/fonts:/fonts \
  riderlty/fontinass:latest
```
设置环境变量`EMBY_SERVER_URL`为你的Emby/Jellyfin服务器的地址

如果你有本地字体，将字体目录映射到`/fonts`下即可自动识别（子文件夹下的文件也会识别）

```
  -v /yourDir/fonts1:/fonts/dir1 \
  -v /yourDir/fonts2:/fonts/dir2 \
  -v /yourDir/fonts3:/fonts/dir3 \
```

> [!NOTE]
> 联网下载的字体存储在/fonts/download</br>即使无本地字体，也建议映射/fonts到主机路径，避免重复下载字体

在客户端上使用`http://[ip]:8012`访问容器代理后的服务器


如果你需要字体缺失/缺少字形日记文件，将日记目录映射到`/logs`下并且设置环境变量（见下）`MISS_LOGS` 或者`MISS_GLYPH_LOGS`

```
  -v /yourDir/fontinass/logs:/logs \
```

如果你需要批量字幕字体子集化，映射8011端口后在网页访问`http://[ip]:8011/subset`（详细功能见下展开）

### 批量字幕子集化介绍

<details>
<summary>（点击展开）</summary>

### 1.界面介绍
打开网页后界面如下所示：  
<img src="image/web_subset_01.png" width="75%">

### 2.如何使用
只需要点击上传或者将文件拖动到界面即可：  
<img src="image/web_subset_02.png" width="75%">

### 3.设置
更多功能可以打开设置，具体详细介绍可以把鼠标放到标题上查看：  
<img src="image/web_subset_03.png" width="75%">

### 4.提示缺失字体或者字形
网上找到对应的字体文件并放入 `fonts` 文件夹后，重新上传文件即可。缺失字形通常也是字体问题，可以尝试使用更新的字体替换。

### 5.提示已有内嵌字体
如果你需要重新嵌入字体，打开界面中的设置并开启`清除内嵌字体`

### 6.我需要子集化后的字体文件
同上打开界面中的设置并开启`下载时附带子集化后字体文件`


</details>

### 无nginx版本
使用```riderlty/fontinass:noproxy```tag，不整合nginx，避免在使用302直链时套壳nginx

有需求的用户可参考手动部署，映射8011端口并配置字幕接口的nginx反向代理```location ~* /videos/(.*)/Subtitles/(.*)/(Stream.ass|Stream.ssa|Stream.srt|Stream.)$```

## Unraid部署

下载模版
``` sh
curl -o /boot/config/plugins/dockerMan/templates-user/my-fontinass.xml  https://raw.githubusercontent.com/RiderLty/fontInAss/refs/heads/main/my-fontinass.xml
```
Docker > 添加容器 > 选择一个模版 > fontinass

修改环境变量并移除你不需要的配置项

应用

## 手动运行
<details>
<summary>（点击展开）</summary>

### 编译c部分
```
python src/py2cy/setup.py
```

### 添加环境变量 EMBY_SERVER_URL
```
EMBY_SERVER_URL = "http://192.168.3.3:7096"
```

### 安装依赖&运行
```
pip install -r ./requirements.txt
python src/main.py
```
或者使用uv（推荐）
```
uv sync
uv run src/main.py
```

### 生成前端文件
```
进入 src/subset
npm run build
```


### 添加nginx反向代理
```
server {
    listen 8012; #新的Emby访问端口
    gzip on;
    gzip_http_version 1.0;
    gzip_comp_level 1;
    gzip_types text/x-ssa;
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

    location ~* /videos/(.*)/Subtitles/(.*)/Stream.vtt  {
        #适配emby网页播放SRT字幕，302直链时避免冲突
        proxy_pass $EMBY_SERVER_URL;
    }

    location ~* /videos/(.*)/Subtitles/(.*)/(Stream.ass|Stream.ssa|Stream.srt|Stream.)$ {
        #仅匹配ass与srt字幕文件，Stream适配infuse
        #修改为你的fontinass服务器地址
        proxy_pass http://127.0.0.1:8011;
    }
        
    location ~* /web/bower_components/(.*)/subtitles-octopus.js {
        #修改为你的fontinass服务器地址
        #如不需要修改web端渲染，可删除此location
        proxy_pass http://127.0.0.1:8011;
    }

    location ~* /web/modules/htmlvideoplayer/plugin.js {
        #修改为你的fontinass服务器地址
        #仅当需要web渲染，且通过https访问时，才需启用此location，否则可删除
        #见 https://github.com/RiderLty/fontInAss/issues/43
        proxy_pass http://127.0.0.1:8011;
    }


    location / {
        #修改为你的Emby/Jellyfin服务器地址
        proxy_pass $EMBY_SERVER_URL;
    }
}
```
</details>

## 关于客户端与播放器
内嵌字体的ASS并非所有播放器都支持，以下为部分播放器（客户端）的支持情况

|         名称          |          平台           |                支持ass内嵌字体                 |
|:-------------------:|:---------------------:|:----------------------------------------:|
|      emby web端      | windows/android/linux | ✅<br/>需要设置`EMBY_WEB_EMBED_FONT`环境变量为True |
|    jellyfin web端    | windows/android/linux |          ✅<br/>jellyfin最新版本已支持           |
|      potplayer      |        windows        |                    ✅                     |
|         mpv         |    windows/android    |                    ✅                     |
|      potplayer      |        windows        |                    ✅                     |
|  Emby for windows   |        windows        |                    ✅                     |
|       tsukimi       |     windows/linux     |                    ✅                     |
|      MX Player      |        android        |                    ✅                     |
|     Exo Player      |        android        |                    ❌                     |
|      Emby 小秘版       |        android        |         ✅<br/>（设置中启用使用mpv播放器后支持）         |
|        hills        |        android        |                    ✅                     |
|        yamby        |        android        |         ✅<br/>（设置中启用使用mpv播放器后支持）         |
|  Emby for Android   |        android        |                    ❌                     |
| Emby for Android TV |        android        |                    ❌                     |
|       infuse        |          ios          |                    ✅                     |
|      SenPlayer      |          ios          |                    ✅                     |
|       vidhub        |          ios          |                    ✅                     |
|    Emby for ios     |          ios          |                    ✅                     |

欢迎补充

## 其他配置说明

容器内部端口`8011`为字体与js处理服务

`8012`为nginx反向代理端口，使用此端口访问代理后的服务器

如有其他需求，可暴露`8011`端口用于字幕处理与HDR设置等

## 配置

| 配置项                        | 描述                                                                    | 默认值       |
|:---------------------------|:----------------------------------------------------------------------|:----------|
| EMBY_WEB_EMBED_FONT        | 修改Emby的字幕渲染文件让Web端也可以正确渲染内嵌字体的字幕<br/>（Jellyfin最新版用户请设置为False，详细说明看下面） | True      |
| RENAMED_FONT_RESTORE       | 还原字幕中被重命名字体的名称                                                        | True      |
| SRT_2_ASS_FORMAT           | 可实现SRT转ASS，统一在不同设备上的播放效果<br/>（Jellyfin无法使用，详细设置看下面）                   | None      |
| SRT_2_ASS_STYLE            | 可实现SRT转ASS，统一在不同设备上的播放效果<br/>（Jellyfin无法使用，详细设置看下面）                   | None      |
| SUB_CACHE_SIZE             | 字幕缓存上限，单位（条）                                                          | 50        |
| SUB_CACHE_TTL              | 字幕缓存在内存的过期时间，单位（分钟），<br/>SUB_CACHE_TTL <= 0 禁用过期                      | 60        |
| FONT_CACHE_SIZE            | 字体缓存上限，单位（条）                                                          | 30        |
| FONT_CACHE_TTL             | 字体缓存在内存的过期时间，单位（分钟），<br/>FONT_CACHE_TTL <= 0 禁用过期                     | 30        |
| NGINX_GZIP_COMP_LEVEL      | nginx的gzip压缩等级,可用值1~9，设置为其他值则禁用gzip（noproxy无作用）                       | 1         |
| LOG_LEVEL                  | 日志等级，可设置为 DEBUG、INFO、WARNING、ERROR、CRITICAL                           | INFO      |
| ERROR_DISPLAY              | 错误信息显示，默认关闭，单位（秒）范围大于0小于60，开启后会在字幕开头插入错误信息用来告知字体缺失或者其他错误信息。           | 0         |
| ERROR_DISPLAY_IGNORE_GLYPH | 错误信息显示开启时，设置为False显示缺少字形+字体缺失信息，设置为True后只会显示字体缺失信息                    | False     |
| MISS_LOGS                  | 字体缺失文件记录开关，设置为True会把字体缺失记录到`MISS_LOGS_NAME`                           | False     |
| MISS_GLYPH_LOGS            | 缺少字形文件记录开关，设置为True会把缺少字形记录到`MISS_LOGS_NAME`                           | False     |
| MISS_LOGS_NAME             | 字体缺失/缺少字形日记文件名，任意中英文/组合（特殊符号除外）                                       | miss_logs |
| MISS_LOGS_SIZE             | 字体缺失/缺少字形日记最大记录数（行数），单位（行）                                            | 20        |
| MISS_LOGS_ORDER            | 字体缺失/缺少字形日记新增顺序，设置为True时新增日记会记录到最后面，反之最前面                             | False     |
> [!NOTE]
> 当 `EMBY_WEB_EMBED_FONT` 设置为 True 时，Nginx 的反向代理会将 Emby 的字幕渲染文件 subtitles-octopus.js 转发给程序处理。程序将在该 JS 文件中新增两个方法：
> </br>1.解析字幕文件获取字体信息
> </br>2.对获取的字体信息的 UUEncode 进行解码，并转为字体文件供字幕渲染文件使用
> </br>需要注意的是，修改原始 JS 文件可能会引发安全性或稳定性问题，请根据实际情况自行斟酌是否启用。
> </br>目前已在 Emby 4.7.14 至 4.9.0.37 版本中测试通过。如果未来 Emby 更新支持内嵌字体功能，可以关闭此项功能。但鉴于 Emby 升级可能存在一定难度，且新版通常不向下兼容，因此该功能可能会长期保留。
> </br> Emby 4.9.0.48b 版本更新加入字幕内嵌字体的支持，经测试开启`EMBY_WEB_EMBED_FONT`不影响，大于该版本可选择关闭这个。

添加环境变量`SRT_2_ASS_FORMAT`与`SRT_2_ASS_STYLE`，可实现SRT转ASS，统一在不同设备上的播放效果（Jellyfin无法使用）
```
  -e SRT_2_ASS_FORMAT='Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding'
  -e SRT_2_ASS_STYLE='Style: Default,楷体,20,&H03FFFFFF,&H00FFFFFF,&H00000000,&H02000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1'
```

通过```http://[ip]:8011/color/set```可调整字幕整体颜色亮度与饱和度，避免HDR显示时过亮(需开放8011端口)


## 关于飞牛影视

可使用fnos的NAS访问地址作为EMBY_SERVER_URL，例如```http://192.168.3.215:5666```

目前测试结果为仅支持WEB端

# 原理说明

## 字体子集化

对字体文件进行处理，仅保留字幕文件用到了的字体，从而缩小字体体积

## 字体嵌入ass
使用UUEncode对子集化后的字体二进制文件进行编码，在ass内添加[Fonts]标签，将编码后字体嵌入字幕（不保证兼容性，部分播放器可能不支持）

## nginx

拦截/videos/(.*)/Subtitles请求，将内容发送到程序处理后，替换原本的内容返回给客户端

# 其他说明

自带的 [onlineFonts.json](https://github.com/RiderLty/fontInAss/blob/main/onlineFonts.json) 文件来自[超级字体整合包 XZ](https://vcb-s.com/archives/1114)
