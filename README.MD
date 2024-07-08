# FontInAss

实时将字体子集化后嵌入ass的小工具

# 原理说明

## 字体子集化

对字体文件进行处理，仅保留字幕文件用到了的字体，从而缩小字体体积

## 字体嵌入ass
使用UUEncode对子集化后的字体二进制文件编码后，在ass文本内添加[Fonts]标签，将字体嵌入字幕（不保证兼容性，因此部分播放器可能不支持）

# 使用方法

## Emby+nginx

拦截/videos/(.*)/Subtitles请求，将内容发送到程序处理后，替换原本的内容返回给客户端

参考 [nginx](https://github.com/RiderLty/fontInAss/tree/main/nginx) 内配置文件

修改端口，emby服务器地址，字幕处理服务器地址

## 调用外部播放器时

如果你使用自定义脚本来添加播放按钮并通过调用外部播放器来播放

只需要在字幕url前添加服务器处理URL的API地址即可 例如 http://localhost:8011/process_url?ass_url=

程序会自动下载原始字幕并返回处理后的字幕

两种使用方法请勿同时开启

# 其他说明

自带的 [fontMap.json](https://github.com/RiderLty/fontInAss/blob/main/fontMap.json) 文件来自[超级字体整合包 XZ](https://vcb-s.com/archives/1114) , 通过cloudflare R2提供

你也可通过内部的 [makeLocalFontsMap.py](https://github.com/RiderLty/fontInAss/blob/main/makeLocalFontsMap.py) 脚本创建自己的本地字体库

程序优先调用本地字体