/**
 * 菜单图标映射：后端 permission.icon（Element 图标名）→ 组件
 * 显式映射（按需，避免全量引入 @element-plus/icons-vue）
 */
import { markRaw, type Component } from 'vue'
import {
  Bell, Box, Briefcase, Calendar, CircleCheck, Connection, CreditCard,
  DataAnalysis, Document, Files, Headset, House, Key, List, Money,
  OfficeBuilding, Setting, ShoppingCart, Stamp, Ticket, Upload, User,
  UserFilled, Wallet,
} from '@element-plus/icons-vue'

const iconMap: Record<string, Component> = {
  Bell: markRaw(Bell),
  Box: markRaw(Box),
  Briefcase: markRaw(Briefcase),
  Calendar: markRaw(Calendar),
  CircleCheck: markRaw(CircleCheck),
  Connection: markRaw(Connection),
  CreditCard: markRaw(CreditCard),
  DataAnalysis: markRaw(DataAnalysis),
  Document: markRaw(Document),
  Files: markRaw(Files),
  Headset: markRaw(Headset),
  House: markRaw(House),
  Key: markRaw(Key),
  List: markRaw(List),
  Money: markRaw(Money),
  OfficeBuilding: markRaw(OfficeBuilding),
  Setting: markRaw(Setting),
  ShoppingCart: markRaw(ShoppingCart),
  Stamp: markRaw(Stamp),
  Ticket: markRaw(Ticket),
  Upload: markRaw(Upload),
  User: markRaw(User),
  UserFilled: markRaw(UserFilled),
  Wallet: markRaw(Wallet),
}

export function useMenuIcon() {
  return (name?: string | null): Component | null => {
    if (!name) return null
    return iconMap[name] || null
  }
}
