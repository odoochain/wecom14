# -*- coding: utf-8 -*-

import logging
import time
from odoo import fields, models, api, Command, tools, _
from odoo.exceptions import UserError
from lxml import etree
from lxml_to_dict import lxml_to_dict
from odoo.addons.wecom_api.api.wecom_abstract_api import ApiException
from odoo.addons.base.models.ir_mail_server import MailDeliveryException

_logger = logging.getLogger(__name__)


class WecomTag(models.Model):
    _name = "wecom.tag"
    _description = "Wecom tag"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        domain="[('is_wecom_organization', '=', True)]",
        copy=False,
        store=True,
    )

    name = fields.Char(string="Name", readonly=True, default="")  # 标签名称
    tagid = fields.Integer(string="Tag ID", readonly=True, default="0",)  # 标签id
    tagname = fields.Char(string="Tag name", readonly=True, default="")  # 标签名称
    userlist = fields.Text(string="User list", readonly=True, default="")  # 标签中包含的成员列表
    partylist = fields.Text(
        string="Party list", readonly=True, default=""
    )  # 标签中包含的部门id列表

    # ------------------------------------------------------------
    # 企微标签下载
    # ------------------------------------------------------------
    @api.model
    def download_wecom_tags(self):
        """
        下载标签列表
        """
        start_time = time.time()
        company = self.env.context.get("company_id")
        tasks = []

        try:
            wxapi = self.env["wecom.service_api"].InitServiceApi(
                company.corpid, company.contacts_app_id.secret
            )
            response = wxapi.httpCall(
                self.env["wecom.service_api_list"].get_server_api_call("TAG_GET_LIST")
            )

        except ApiException as ex:
            end_time = time.time()
            self.env["wecomapi.tools.action"].ApiExceptionDialog(
                ex, raise_exception=False
            )
            tasks = [
                {
                    "name": "download_tag_data",
                    "state": False,
                    "time": end_time - start_time,
                    "msg": str(ex),
                }
            ]
        except Exception as e:
            end_time = time.time()

            tasks = [
                {
                    "name": "download_tag_data",
                    "state": False,
                    "time": end_time - start_time,
                    "msg": str(e),
                }
            ]
        else:
            wecom_tags = response["taglist"]  # 列表类型数据

            # 下载标签
            for wecom_tag in wecom_tags:
                download_tag_result = self.download_tag(company, wecom_tag)
                if download_tag_result:
                    for r in download_tag_result:
                        tasks.append(r)  # 加入 下载标签失败结果

        finally:
            end_time = time.time()
            task = {
                "name": "download_tag_data",
                "state": True,
                "time": end_time - start_time,
                "msg": _("Tag list downloaded successfully."),
            }
            tasks.append(task)

    def download_tag(self, company, wecom_tag):
        """
        下载标签
        """
        tag = self.sudo().search(
            [("tagid", "=", wecom_tag["tagid"]), ("company_id", "=", company.id),],
            limit=1,
        )
        result = {}
        try:
            wxapi = self.env["wecom.service_api"].InitServiceApi(
                company.corpid, company.contacts_app_id.secret
            )

            response = wxapi.httpCall(
                self.env["wecom.service_api_list"].get_server_api_call(
                    "TAG_GET_MEMBER"
                ),
                {"tagid": wecom_tag["tagid"]},
            )
            wecom_tag.update(
                {
                    "userlist": self.env["wecom.tools"].check_dictionary_keywords(
                        response, "userlist"
                    ),
                    "partylist": self.env["wecom.tools"].check_dictionary_keywords(
                        response, "partylist"
                    ),
                }
            )

        except ApiException as ex:
            result = _(
                "Wecom API acquisition company[%s]'s tag [id:%s] member failed, error details: %s"
            ) % (company.name, wecom_tag["tagid"], str(ex))
            _logger.warning(result)
        except Exception as e:
            result = _(
                "Wecom API acquisition company[%s]'s tag [id:%s] member failed, error details: %s"
            ) % (company.name, wecom_tag["tagid"], str(e))
            _logger.warning(result)
        else:
            if not tag:
                result = self.create_tag(company, tag, wecom_tag)
            else:
                result = self.update_tag(company, tag, wecom_tag)
        finally:
            return result

    def create_tag(self, company, tag, wecom_tag):
        """
        创建标签
        """
        try:
            tag.create(
                {
                    "tagname": wecom_tag["tagname"],
                    "tagid": wecom_tag["tagid"],
                    "userlist": wecom_tag["userlist"],
                    "partylist": wecom_tag["partylist"],
                    "company_id": company.id,
                }
            )
        except Exception as e:
            result = _("Error creating company [%s] tag [%s], error reason: %s") % (
                company.name,
                wecom_tag["tagname"],
                repr(e),
            )

            _logger.warning(result)
            return {
                "name": "add_tag",
                "state": False,
                "time": 0,
                "msg": result,
            }  # 返回失败结果

    def update_tag(self, company, tag, wecom_tag):
        """
        更新标签
        """
        try:
            tag.write(
                {
                    "tagname": wecom_tag["tagname"],
                    "userlist": wecom_tag["userlist"],
                    "partylist": wecom_tag["partylist"],
                }
            )
        except Exception as e:
            result = _("Error update company [%s] tag [%s], error reason: %s") % (
                company.name,
                wecom_tag["tagname"],
                repr(e),
            )

            _logger.warning(result)
            return {
                "name": "update_tag",
                "state": False,
                "time": 0,
                "msg": result,
            }  # 返回失败结果
