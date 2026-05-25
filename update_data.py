import json, os

products = [
  {"id":"P001","name":"经典纯棉T恤","category":"上装/T恤","price":89.0,"original_price":119.0,"material":"100%新疆长绒棉","colors":["白色","黑色","灰色","藏青色"],"sizes":["S","M","L","XL","XXL"],"description":"采用新疆长绒棉，亲肤透气，经典圆领设计，适合日常穿着。面料克重200g，不易变形。","image_url":"https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=400&h=400&fit=crop","size_chart":{"S":"胸围92cm 衣长66cm","M":"胸围98cm 衣长68cm","L":"胸围104cm 衣长70cm","XL":"胸围110cm 衣长72cm","XXL":"胸围116cm 衣长74cm"},"care_instructions":"可机洗，水温不超过30度，不可漂白，低温熨烫","tags":["基础款","百搭","纯棉","四季可穿"],"stock_status":"充足","sales_count":3280},
  {"id":"P002","name":"修身牛仔裤","category":"下装/牛仔裤","price":259.0,"original_price":329.0,"material":"98%棉 2%氨纶","colors":["深蓝色","浅蓝色","黑色"],"sizes":["28","29","30","31","32","33","34"],"description":"修身版型，微弹面料，经典五袋设计，水洗工艺自然，穿着舒适不紧绷。","image_url":"https://images.unsplash.com/photo-1542272604-787c3835535d?w=400&h=400&fit=crop","size_chart":{"28":"腰围71cm 臀围90cm 裤长100cm","29":"腰围73.5cm 臀围92.5cm 裤长101cm","30":"腰围76cm 臀围95cm 裤长102cm","31":"腰围78.5cm 臀围97.5cm 裤长103cm","32":"腰围81cm 臀围100cm 裤长104cm","33":"腰围83.5cm 臀围102.5cm 裤长105cm","34":"腰围86cm 臀围105cm 裤长106cm"},"care_instructions":"反面洗涤，冷水手洗或机洗，不可漂白","tags":["经典","修身","百搭","四季可穿"],"stock_status":"充足","sales_count":2150},
  {"id":"P003","name":"轻薄羽绒服","category":"外套/羽绒服","price":599.0,"original_price":899.0,"material":"面料:100%涤纶 填充:90%白鸭绒","colors":["黑色","藏青色","军绿色","卡其色"],"sizes":["M","L","XL","XXL"],"description":"轻薄保暖，90%白鸭绒填充，蓬松度700+，立领设计，可收纳折叠，方便携带。","image_url":"https://images.unsplash.com/photo-1544923246-77307dd270aa?w=400&h=400&fit=crop","size_chart":{"M":"胸围108cm 衣长68cm","L":"胸围114cm 衣长70cm","XL":"胸围120cm 衣长72cm","XXL":"胸围126cm 衣长74cm"},"care_instructions":"建议干洗，如水洗请使用中性洗涤剂，不可拧干","tags":["保暖","轻薄","秋冬","鸭绒"],"stock_status":"部分色号紧张","sales_count":1890},
  {"id":"P004","name":"碎花连衣裙","category":"裙装/连衣裙","price":329.0,"original_price":459.0,"material":"100%雪纺","colors":["花色A","花色B","花色C"],"sizes":["S","M","L","XL"],"description":"法式碎花设计，V领收腰，A字裙摆，优雅浪漫，内衬防走光，裙长及膝。","image_url":"https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?w=400&h=400&fit=crop","size_chart":{"S":"胸围84cm 腰围66cm 裙长110cm","M":"胸围88cm 腰围70cm 裙长112cm","L":"胸围92cm 腰围74cm 裙长114cm","XL":"胸围96cm 腰围78cm 裙长116cm"},"care_instructions":"手洗推荐，冷水洗涤，不可漂白，阴凉处晾干","tags":["碎花","连衣裙","春夏","法式"],"stock_status":"充足","sales_count":1560},
  {"id":"P005","name":"运动卫衣","category":"上装/卫衣","price":199.0,"original_price":269.0,"material":"80%棉 20%涤纶","colors":["黑色","灰色","白色","粉色"],"sizes":["S","M","L","XL","XXL"],"description":"宽松版型，加绒内里，连帽设计，面料柔软不起球，帽檐有抽绳调节。","image_url":"https://images.unsplash.com/photo-1556821840-3a63f95609a7?w=400&h=400&fit=crop","size_chart":{"S":"胸围106cm 衣长67cm","M":"胸围112cm 衣长69cm","L":"胸围118cm 衣长71cm","XL":"胸围124cm 衣长73cm","XXL":"胸围130cm 衣长75cm"},"care_instructions":"可机洗，水温不超过30度，不可漂白","tags":["卫衣","加绒","运动","秋冬"],"stock_status":"充足","sales_count":2760},
  {"id":"P006","name":"商务休闲POLO衫","category":"上装/POLO衫","price":159.0,"original_price":219.0,"material":"60%棉 40%涤纶 珠地网眼面料","colors":["白色","黑色","深蓝色","灰色","军绿色"],"sizes":["S","M","L","XL","XXL"],"description":"珠地网眼面料，透气排汗，经典翻领设计，商务休闲两相宜。版型合体不紧身。","image_url":"https://images.unsplash.com/photo-1586363104862-3a5e2ab60d99?w=400&h=400&fit=crop","size_chart":{"S":"胸围96cm 衣长67cm","M":"胸围102cm 衣长69cm","L":"胸围108cm 衣长71cm","XL":"胸围114cm 衣长73cm","XXL":"胸围120cm 衣长75cm"},"care_instructions":"可机洗，水温不超过40度，不可漂白，中温熨烫","tags":["POLO衫","商务","休闲","通勤"],"stock_status":"充足","sales_count":1920},
  {"id":"P007","name":"亚麻短袖衬衫","category":"上装/衬衫","price":199.0,"original_price":279.0,"material":"100%天然亚麻","colors":["白色","米色","浅蓝色","卡其色"],"sizes":["S","M","L","XL"],"description":"天然亚麻面料，透气凉爽，自带褶皱质感，日系文艺风格。适合夏季单穿或春秋内搭。","image_url":"https://images.unsplash.com/photo-1596755094514-f87e34085b2c?w=400&h=400&fit=crop","size_chart":{"S":"胸围100cm 衣长70cm","M":"胸围106cm 衣长72cm","L":"胸围112cm 衣长74cm","XL":"胸围118cm 衣长76cm"},"care_instructions":"建议手洗或干洗，不可机洗甩干，阴凉处晾干","tags":["亚麻","衬衫","夏季","文艺"],"stock_status":"充足","sales_count":870},
  {"id":"P008","name":"弹力休闲裤","category":"下装/休闲裤","price":189.0,"original_price":249.0,"material":"68%棉 28%涤纶 4%氨纶","colors":["黑色","深灰色","卡其色","藏青色"],"sizes":["28","29","30","31","32","33","34","36"],"description":"高弹力面料，修身直筒版型，松紧腰设计，穿着舒适无束缚。适合日常通勤和休闲。","image_url":"https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?w=400&h=400&fit=crop","size_chart":{"28":"腰围72cm 臀围92cm 裤长100cm","30":"腰围77cm 臀围97cm 裤长102cm","32":"腰围82cm 臀围102cm 裤长104cm","34":"腰围87cm 臀围107cm 裤长106cm","36":"腰围92cm 臀围112cm 裤长108cm"},"care_instructions":"可机洗，冷水洗涤，不可漂白，低温烘干","tags":["休闲裤","弹力","通勤","舒适"],"stock_status":"充足","sales_count":1640},
  {"id":"P009","name":"牛津纺衬衫","category":"上装/衬衫","price":179.0,"original_price":239.0,"material":"100%纯棉牛津纺","colors":["白色","浅蓝色","粉色","灰色"],"sizes":["S","M","L","XL","XXL"],"description":"经典牛津纺面料，质感厚实，领口有纽扣固定，休闲又不失正式。可单穿也可搭配西装外套。","image_url":"https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?w=400&h=400&fit=crop","size_chart":{"S":"胸围98cm 衣长69cm","M":"胸围104cm 衣长71cm","L":"胸围110cm 衣长73cm","XL":"胸围116cm 衣长75cm","XXL":"胸围122cm 衣长77cm"},"care_instructions":"可机洗，水温不超过40度，可低温熨烫","tags":["衬衫","牛津纺","商务休闲","百搭"],"stock_status":"充足","sales_count":1380},
  {"id":"P010","name":"工装短裤","category":"下装/短裤","price":149.0,"original_price":199.0,"material":"100%纯棉帆布","colors":["军绿色","卡其色","黑色","深灰色"],"sizes":["S","M","L","XL","XXL"],"description":"宽松版型，多口袋工装设计，纯棉帆布面料耐磨耐穿。裤长在膝盖上方，适合夏季。","image_url":"https://images.unsplash.com/photo-1591195853828-11db59a44f6b?w=400&h=400&fit=crop","size_chart":{"S":"腰围74cm 裤长48cm","M":"腰围78cm 裤长50cm","L":"腰围82cm 裤长52cm","XL":"腰围86cm 裤长54cm","XXL":"腰围90cm 裤长56cm"},"care_instructions":"可机洗，冷水洗涤，可漂白，中温熨烫","tags":["短裤","工装","夏季","休闲"],"stock_status":"充足","sales_count":980},
  {"id":"P011","name":"针织开衫","category":"外套/针织衫","price":239.0,"original_price":329.0,"material":"50%羊毛 50%腈纶","colors":["驼色","灰色","深蓝色","黑色"],"sizes":["S","M","L","XL"],"description":"含羊毛混纺面料，柔软亲肤，V领开襟设计，单排扣，适合春秋外搭或冬日内搭。","image_url":"https://images.unsplash.com/photo-1434389677669-e08b4cda3a11?w=400&h=400&fit=crop","size_chart":{"S":"胸围100cm 衣长62cm","M":"胸围106cm 衣长64cm","L":"胸围112cm 衣长66cm","XL":"胸围118cm 衣长68cm"},"care_instructions":"建议干洗或手洗，平铺晾干，不可机洗甩干","tags":["针织","开衫","羊毛","春秋"],"stock_status":"充足","sales_count":1120},
  {"id":"P012","name":"棒球领夹克","category":"外套/夹克","price":359.0,"original_price":499.0,"material":"面料:100%涤纶 内衬:100%涤纶","colors":["黑色","军绿色","藏青色"],"sizes":["M","L","XL","XXL"],"description":"棒球领设计，罗纹袖口和下摆，拉链开合，两侧插袋。运动休闲风格，适合春秋季节。","image_url":"https://images.unsplash.com/photo-1551028719-00167b16eac5?w=400&h=400&fit=crop","size_chart":{"M":"胸围110cm 衣长65cm","L":"胸围116cm 衣长67cm","XL":"胸围122cm 衣长69cm","XXL":"胸围128cm 衣长71cm"},"care_instructions":"可机洗，冷水洗涤，不可漂白，不可烘干","tags":["夹克","棒球领","运动","春秋"],"stock_status":"充足","sales_count":760},
  {"id":"P013","name":"高腰A字半身裙","category":"裙装/半身裙","price":189.0,"original_price":259.0,"material":"95%涤纶 5%氨纶","colors":["黑色","卡其色","深蓝色","墨绿色"],"sizes":["S","M","L","XL"],"description":"高腰设计拉长腿部线条，A字版型修饰臀胯，侧拉链，内衬防走光。通勤休闲两用。","image_url":"https://images.unsplash.com/photo-1583496661160-fb5886a0aaaa?w=400&h=400&fit=crop","size_chart":{"S":"腰围64cm 裙长42cm","M":"腰围68cm 裙长43cm","L":"腰围72cm 裙长44cm","XL":"腰围76cm 裙长45cm"},"care_instructions":"可机洗，冷水洗涤，不可漂白，低温熨烫","tags":["半身裙","高腰","A字裙","通勤"],"stock_status":"充足","sales_count":1340},
  {"id":"P014","name":"纯棉格子衬衫","category":"上装/衬衫","price":169.0,"original_price":229.0,"material":"100%纯棉","colors":["红格","蓝格","绿格","黄格"],"sizes":["S","M","L","XL","XXL"],"description":"经典格纹，纯棉面料柔软舒适，直筒版型，可单穿也可系在腰间做装饰。美式休闲风格。","image_url":"https://images.unsplash.com/photo-1598032895397-b9472444bf93?w=400&h=400&fit=crop","size_chart":{"S":"胸围100cm 衣长68cm","M":"胸围106cm 衣长70cm","L":"胸围112cm 衣长72cm","XL":"胸围118cm 衣长74cm","XXL":"胸围124cm 衣长76cm"},"care_instructions":"可机洗，水温不超过40度，可低温熨烫，首次洗涤可能轻微掉色","tags":["格子","衬衫","休闲","美式"],"stock_status":"充足","sales_count":1050},
  {"id":"P015","name":"束脚运动裤","category":"下装/运动裤","price":139.0,"original_price":189.0,"material":"65%棉 35%涤纶","colors":["黑色","灰色","深蓝色"],"sizes":["S","M","L","XL","XXL"],"description":"束脚设计，松紧腰抽绳，侧边口袋，运动休闲两用面料，柔软透气。适合运动和居家。","image_url":"https://images.unsplash.com/photo-1552902865-b72c031ac5ea?w=400&h=400&fit=crop","size_chart":{"S":"腰围68cm 臀围100cm 裤长96cm","M":"腰围72cm 臀围104cm 裤长98cm","L":"腰围76cm 臀围108cm 裤长100cm","XL":"腰围80cm 臀围112cm 裤长102cm","XXL":"腰围84cm 臀围116cm 裤长104cm"},"care_instructions":"可机洗，水温不超过30度，不可漂白","tags":["运动裤","束脚","休闲","舒适"],"stock_status":"充足","sales_count":2080},
  {"id":"P016","name":"羊毛混纺大衣","category":"外套/大衣","price":699.0,"original_price":999.0,"material":"70%羊毛 30%涤纶","colors":["驼色","黑色","深灰色","藏青色"],"sizes":["M","L","XL","XXL"],"description":"含羊毛混纺面料，质感厚实挺括，双排扣设计，中长款，气场十足。适合秋冬通勤。","image_url":"https://images.unsplash.com/photo-1544923246-77307dd270aa?w=400&h=400&fit=crop","size_chart":{"M":"胸围112cm 衣长95cm","L":"胸围118cm 衣长97cm","XL":"胸围124cm 衣长99cm","XXL":"胸围130cm 衣长101cm"},"care_instructions":"建议干洗，不可机洗，悬挂存放，避免挤压","tags":["大衣","羊毛","秋冬","通勤"],"stock_status":"部分尺码紧张","sales_count":680},
  {"id":"P017","name":"印花圆领长袖T恤","category":"上装/T恤","price":129.0,"original_price":179.0,"material":"95%棉 5%氨纶","colors":["白色","黑色","灰色"],"sizes":["S","M","L","XL","XXL"],"description":"前胸创意印花，微弹纯棉面料，圆领设计，版型宽松，适合春秋单穿或冬季内搭。","image_url":"https://images.unsplash.com/photo-1576566588028-4147f3842f27?w=400&h=400&fit=crop","size_chart":{"S":"胸围98cm 衣长68cm","M":"胸围104cm 衣长70cm","L":"胸围110cm 衣长72cm","XL":"胸围116cm 衣长74cm","XXL":"胸围122cm 衣长76cm"},"care_instructions":"可机洗，水温不超过30度，反面洗涤保护印花，不可漂白","tags":["长袖","印花","春秋","潮流"],"stock_status":"充足","sales_count":920},
  {"id":"P018","name":"西装裤","category":"下装/西裤","price":229.0,"original_price":319.0,"material":"70%涤纶 28%粘纤 2%氨纶","colors":["黑色","深灰色","藏青色"],"sizes":["28","29","30","31","32","33","34","36"],"description":"修身直筒版型，面料垂感好不易皱，拉链+纽扣门襟，两侧斜插袋。通勤正装首选。","image_url":"https://images.unsplash.com/photo-1594938298603-c8148c4dae35?w=400&h=400&fit=crop","size_chart":{"28":"腰围72cm 臀围94cm 裤长102cm","30":"腰围77cm 臀围99cm 裤长104cm","32":"腰围82cm 臀围104cm 裤长106cm","34":"腰围87cm 臀围109cm 裤长108cm","36":"腰围92cm 臀围114cm 裤长110cm"},"care_instructions":"可机洗，冷水洗涤，低温熨烫，悬挂晾干","tags":["西裤","通勤","正装","修身"],"stock_status":"充足","sales_count":1450},
  {"id":"P019","name":"纯棉polo短袖","category":"上装/POLO衫","price":139.0,"original_price":189.0,"material":"100%纯棉珠地棉","colors":["白色","黑色","深蓝色","酒红色","墨绿色"],"sizes":["S","M","L","XL","XXL"],"description":"纯棉珠地面料，透气吸汗，经典翻领三粒扣，修身版型。适合商务休闲和高尔夫运动。","image_url":"https://images.unsplash.com/photo-1625910513413-5fc429e2ac63?w=400&h=400&fit=crop","size_chart":{"S":"胸围94cm 衣长66cm","M":"胸围100cm 衣长68cm","L":"胸围106cm 衣长70cm","XL":"胸围112cm 衣长72cm","XXL":"胸围118cm 衣长74cm"},"care_instructions":"可机洗，水温不超过40度，不可漂白，中温熨烫","tags":["POLO衫","纯棉","商务","夏季"],"stock_status":"充足","sales_count":1680},
  {"id":"P020","name":"连帽防晒衣","category":"外套/防晒衣","price":169.0,"original_price":239.0,"material":"100%涤纶 UPF50+防晒面料","colors":["白色","浅灰色","粉色","浅蓝色"],"sizes":["S","M","L","XL"],"description":"UPF50+防晒指数，轻薄透气，连帽设计，可收纳至口袋，方便携带。适合户外防晒。","image_url":"https://images.unsplash.com/photo-1544923246-77307dd270aa?w=400&h=400&fit=crop","size_chart":{"S":"胸围104cm 衣长64cm","M":"胸围110cm 衣长66cm","L":"胸围116cm 衣长68cm","XL":"胸围122cm 衣长70cm"},"care_instructions":"可机洗，冷水洗涤，不可漂白，不可烘干","tags":["防晒衣","夏季","户外","轻薄"],"stock_status":"充足","sales_count":2340}
]

faq = [
  {"question":"如何选择合适的尺码？","answer":"请参考商品详情页的尺码表，根据您的身高、体重、胸围、腰围等数据选择。如果您在两个尺码之间，建议选大一号。如有疑问可咨询客服获取个性化建议。"},
  {"question":"支持哪些付款方式？","answer":"我们支持微信支付、支付宝、银行卡、信用卡、花呗分期（3/6/12期）等多种付款方式。分期手续费由平台承担，用户免息。"},
  {"question":"发货时效是多久？","answer":"普通商品下单后48小时内发货，预售商品会标注预计发货时间。节假日可能有所延迟。急单可在备注中注明，我们会优先处理。"},
  {"question":"发什么快递？","answer":"默认发中通/圆通快递，偏远地区发邮政EMS。如需指定快递（顺丰、京东等），下单时备注即可，可能需补差价。"},
  {"question":"包邮吗？","answer":"全国大部分地区满99元包邮（新疆、西藏、港澳台除外）。不满99元收取8元运费。新疆/西藏地区运费15元。"},
  {"question":"可以修改订单吗？","answer":"未发货订单可以修改收货地址和联系方式，请在订单详情页操作或联系客服。已发货订单无法修改，可收货后申请退换。"},
  {"question":"如何申请退换货？","answer":"收到商品后7天内，在商品未穿着、未洗涤、吊牌完好的情况下，可在订单详情页申请退换货。退换货需提供商品照片作为凭证。"},
  {"question":"退换货运费谁承担？","answer":"因质量问题退换货，运费由我们承担（最高补偿12元）；非质量问题（如尺码不合适、不喜欢等）退换货运费由买家承担。"},
  {"question":"退款多久到账？","answer":"退货商品验收合格后，退款将在1-3个工作日内原路返回。支付宝/微信一般即时到账，银行卡可能需要3-5个工作日。"},
  {"question":"会员有什么权益？","answer":"注册即为普通会员，消费满500元升级银卡会员（9.5折），满2000元升级金卡会员（9折），满5000元升级钻石会员（8.5折）。会员还享受生日礼券、优先发货、专属客服、每月会员日专属折扣等权益。"},
  {"question":"有哪些优惠活动？","answer":"我们定期举办满减活动（满200减30、满500减80）、新客首单9折、季节清仓特惠、会员日专属折扣、双11/618大促等。请关注我们的公众号获取最新优惠信息。"},
  {"question":"商品有色差怎么办？","answer":"由于拍摄光线和显示器色差，实物颜色可能与图片略有差异，属正常范围。如色差严重影响穿着，可在7天内申请退换货。"},
  {"question":"衣服缩水怎么办？","answer":"建议按照商品洗涤标签说明洗涤。纯棉衣物首次洗涤可能有1-2%的正常缩水，建议不要用热水洗涤。如缩水严重属于质量问题，可联系客服退换。"},
  {"question":"可以开发票吗？","answer":"可以开具电子普通发票，下单时在备注中注明发票信息（抬头、税号）即可，发货后3个工作日内发送至您的邮箱。"},
  {"question":"线下有门店吗？","answer":"目前我们是纯线上品牌，暂无实体门店。但支持7天无理由退换货，您可以放心购买。未来计划在北京、上海、杭州开设体验店。"},
  {"question":"怎么联系客服？","answer":"您可以通过以下方式联系我们：1. 在线客服（本页面右下角）2. 微信公众号衣尚优品 3. 客服电话 400-888-6688（工作日 9:00-18:00）4. 邮箱 service@yishangyoupin.com"},
  {"question":"商品多久补货？","answer":"热销商品一般1-2周补货一次。您可以在商品页面点击到货通知，补货后会第一时间通知您。限量款售罄后不再补货。"},
  {"question":"买多件有优惠吗？","answer":"部分商品支持买2件减20、买3件减50等活动，具体以商品页面标注为准。金卡及以上会员可叠加会员折扣。"},
  {"question":"衣服起球了怎么办？","answer":"少量起球属正常现象，可用毛球修剪器处理。如大面积起球属于质量问题，请拍照联系客服，我们会在7天内为您处理退换。"},
  {"question":"预售商品什么时候发货？","answer":"预售商品会在商品页面标注预计发货时间，一般为下单后7-15天。如遇延迟我们会主动联系您。预售商品支持随时取消退款。"}
]

os.makedirs("data/docs", exist_ok=True)
with open("data/docs/products.json", "w", encoding="utf-8") as f:
    json.dump(products, f, ensure_ascii=False, indent=2)
with open("data/docs/faq.json", "w", encoding="utf-8") as f:
    json.dump(faq, f, ensure_ascii=False, indent=2)

styling_guide = """
# 穿搭搭配指南

## 春季搭配

### 男生春季
- 纯棉T恤 + 修身牛仔裤 + 运动鞋：干净利落的日常通勤装
- 牛津纺衬衫 + 休闲裤 + 乐福鞋：轻商务休闲
- 卫衣 + 束脚运动裤 + 帆布鞋：校园潮流风
- 针织开衫 + T恤 + 牛仔裤：文艺暖男风

### 女生春季
- 碎花连衣裙 + 针织开衫 + 单鞋：温柔淑女风
- T恤 + 高腰半身裙 + 小白鞋：简约清新
- 卫衣 + 牛仔裤 + 运动鞋：休闲百搭
- 针织衫 + A字半身裙 + 短靴：知性优雅

## 夏季搭配

### 男生夏季
- T恤 + 工装短裤 + 凉鞋：清爽简约
- POLO衫 + 休闲裤 + 乐福鞋：商务休闲
- 亚麻衬衫 + 短裤 + 草编鞋：度假文艺风
- 纯棉T恤 + 束脚运动裤 + 运动鞋：运动休闲

### 女生夏季
- 碎花连衣裙 + 草编包 + 凉鞋：法式度假风
- T恤 + 高腰A字裙 + 帆布鞋：学生清新
- 印花长袖T恤 + 短裤 + 运动鞋：街头个性
- 亚麻衬衫 + 半身裙 + 单鞋：文艺复古

## 秋季搭配

### 男生秋季
- 卫衣 + 牛仔裤 + 运动鞋：舒适休闲
- 针织开衫 + 衬衫 + 休闲裤：层次叠穿
- 棒球领夹克 + T恤 + 牛仔裤：街头运动风
- 牛津纺衬衫 + 西装裤 + 皮鞋：轻商务

### 女生秋季
- 针织衫 + 半身裙 + 短靴：优雅知性
- 卫衣 + 牛仔裤 + 运动鞋：休闲舒适
- 轻薄羽绒服 + 卫衣 + 牛仔裤：保暖实用
- 大衣 + 高领毛衣 + 阔腿裤：气场全开

## 冬季搭配

### 男生冬季
- 羽绒服 + 卫衣 + 束脚运动裤 + 运动鞋：保暖运动
- 羊毛大衣 + 高领毛衣 + 西装裤 + 短靴：型男商务
- 羽绒服 + 针织衫 + 牛仔裤 + 靴子：保暖日常
- 棒球领夹克 + 卫衣 + 休闲裤 + 运动鞋：街头保暖

### 女生冬季
- 羽绒服 + 毛衣 + 加绒裤 + 靴子：保暖至上
- 大衣 + 高领毛衣 + 阔腿裤 + 短靴：气场全开
- 卫衣 + 羽绒马甲 + 束脚裤 + 运动鞋：运动保暖
- 针织开衫 + 连衣裙 + 长靴：温柔知性

## 场合穿搭建议

### 日常通勤
- 男生：牛津纺衬衫 + 西装裤 + 皮鞋，简约干练
- 女生：高腰半身裙 + 针织衫 + 单鞋，知性优雅

### 约会穿搭
- 男生：针织开衫 + T恤 + 休闲裤，温柔不刻意
- 女生：碎花连衣裙 + 针织开衫 + 单鞋，甜美浪漫

### 朋友聚会
- 男生：印花T恤 + 牛仔裤 + 运动鞋，随性自在
- 女生：卫衣 + 半身裙 + 帆布鞋，活力青春

### 户外运动
- 男生：运动卫衣 + 束脚运动裤 + 运动鞋，舒适透气
- 女生：运动卫衣 + 运动裤 + 运动鞋，活力满满

## 体型搭配建议

### 偏瘦体型
- 选择有层次感的叠穿（如T恤+衬衫+外套），浅色系增加视觉丰满感
- 避免过于宽松的衣服，选择合身或略修身的版型
- 横条纹可以在视觉上增加宽度

### 偏胖体型
- 选择V领、竖条纹，深色系更显瘦
- 避免过于宽松或过于紧身，选择合体版型
- 上衣扎进裤子，提高腰线拉长比例
- 外套选择有肩线的款式，避免落肩

### 娇小体型（男<170cm，女<158cm）
- 高腰线是关键，选择短款上衣+高腰下装
- 同色系穿搭在视觉上拉长身形
- 避免过于宽大的衣服和过长的裤脚
- 选择尖头鞋或V口鞋延伸腿部线条

### 高个子体型（男>185cm，女>170cm）
- 可以尝试长款大衣、阔腿裤等大气款式
- 层次叠穿能平衡身材比例
- 避免过多竖条纹，横条纹和图案可以增加视觉宽度
- 选择宽松版型更显随性

## 色彩搭配技巧

### 基础配色法则
- **同色系**：深浅不同的同一颜色，高级感强（如深蓝+浅蓝）
- **互补色**：色轮对面的颜色，视觉冲击力强（如蓝+橙）
- **邻近色**：色轮相邻的颜色，和谐自然（如蓝+绿）

### 安全配色组合
- 黑色 + 白色：经典永不过时
- 藏青色 + 白色：干净清爽
- 灰色 + 黑色：高级质感
- 卡其色 + 白色：温柔知性
- 军绿色 + 黑色：酷帅有型

### 配色小技巧
- 全身颜色不超过3种，避免杂乱
- 亮色单品搭配中性色（黑、白、灰、藏青）更安全
- 配饰（包、鞋、帽子）可以作为点缀色呼应整体
- 肤色偏黄避免大面积使用黄色、橘色
- 肤色偏白可以大胆尝试各种颜色
"""

with open("data/docs/styling_guide.md", "w", encoding="utf-8") as f:
    f.write(styling_guide)
print(f"Done: {len(products)} products, {len(faq)} FAQ, styling_guide.md updated")
