from django.db import models


# class TokenPrice(models.Model):
#     name = models.CharField('名称', max_length=20)
#     signal = models.CharField('signal', max_length=20)
#     origin_price = models.BigIntegerField('原始价格')
#     roi_week = models.FloatField('roi_week')
#     created_time = models.DateTimeField('创建时间', auto_now_add=True)
#
#     def __str__(self):
#         return self.name


class TokenJson(models.Model):
    text = models.TextField('文本')
    created_time = models.DateTimeField('创建时间', auto_now_add=True)
