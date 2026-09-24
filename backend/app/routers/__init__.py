"""业务模块路由汇总。

这里统一按别名导入再暴露 ROUTERS：模块名有可能和内置名撞车（某个业务模块就叫 dict、list
这种名字时），按名字直接 import 会把内置类型覆盖掉，函数注解在运行时求值就会报
'module' object is not subscriptable。
"""
from __future__ import annotations

from app.routers import station as router_station
from app.routers import sensor as router_sensor
from app.routers import observation as router_observation
from app.routers import quality as router_quality
from app.routers import calibration as router_calibration
from app.routers import transmission as router_transmission
from app.routers import power as router_power
from app.routers import layout as router_layout
from app.routers import inspection as router_inspection
from app.routers import fault as router_fault
from app.routers import sparepart as router_sparepart
from app.routers import metainfo as router_metainfo
from app.routers import alarm as router_alarm
from app.routers import comm as router_comm
from app.routers import service as router_service
from app.routers import contract as router_contract
from app.routers import settlement as router_settlement
from app.routers import training as router_training

ROUTERS = [router_station, router_sensor, router_observation, router_quality, router_calibration, router_transmission, router_power, router_layout, router_inspection, router_fault, router_sparepart, router_metainfo, router_alarm, router_comm, router_service, router_contract, router_settlement, router_training]
