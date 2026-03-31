---
layout: page
title: 角落
permalink: /corner/
comments: false
toc: false
---

这里放一些面试记录和碎碎念，不进主导航。

{% assign interview_posts = site.interview | sort: "date" | reverse %}

{% if interview_posts.size > 0 %}
{% for post in interview_posts %}
### [{{ post.title }}]({{ post.url | relative_url }})

- {{ post.date | date: "%Y-%m-%d" }}{% if post.tags and post.tags.size > 0 %} · {{ post.tags | join: " / " }}{% endif %}

{{ post.excerpt | strip_html | strip }}

{% endfor %}
{% else %}
暂时还没有内容。
{% endif %}
