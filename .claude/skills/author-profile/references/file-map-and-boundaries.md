# 文件地图与职责边界

## 核心文件

- `author-profile/PROFILE.md`
  - 高密度作者画像，给 agent 快速建立稳定认识
  - 主要放：事实、技术判断、思考方式、知识盲区、风格偏好
  - 要求：短、稳、去重，控制在 150 行左右

- `_not_publish/经历与思考素材库.md`
  - 写博客时可直接调用的认知转折素材
  - 主要放：具体场景、误解、转折、修改、现在的判断
  - 要求：一条卡片只讲一个认知点

- `_not_publish/中科曙光经历.md`
- `_not_publish/蚂蚁金服ob经历.md`
- `_not_publish/jianli.md`
  - 经历原始材料和结构化履历
  - 主要放：完整项目背景、工作内容、性能数据、职责边界、可被深挖的细节

- `author-profile/scripts/check_author_profile.py`
  - 轻量一致性检查
  - 检查项：`PROFILE.md` 是否过长/重复，素材卡片是否缺关键字段，经历文件结构是否明显缺项

## 与 `new-or-review` 的职责边界

`author-profile` 是作者画像和素材的系统记录，`new-or-review` 是写作与审稿工作流。

- `author-profile` 负责：
  - 维护稳定事实、长期偏好、认知转折素材、经历文件校准

- `new-or-review` 负责：
  - 访谈、列提纲、写首稿、审稿、调用检测器、做局部修订

- 两者联动方式：
  - `new-or-review` 写前先读这里
  - `new-or-review` 写后或改后，如果拿到新的稳定信息，再回写这里

如果两个 skill 的描述冲突，以这里维护的画像和素材文件为准；`new-or-review` 里的作者约束应视为操作化镜像，不是独立真相源。

## 默认读文件顺序

触发后按这个顺序读：

1. `author-profile/PROFILE.md`
2. `_not_publish/经历与思考素材库.md`
3. 如果本次话题涉及具体实习或项目，再读对应经历文件
4. 如果涉及简历表述、时间线、项目范围，再读 `_not_publish/jianli.md`

不要每次都把所有文件全读一遍。只读和当前话题直接相关的部分。
