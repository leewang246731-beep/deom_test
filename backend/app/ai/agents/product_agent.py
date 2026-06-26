"""ProductAgent — 商品搜索与库存查询专家"""
from app.ai.agents.base_agent import BaseExpertAgent
from app.database.session import SessionLocal
from app.models.external_product import ExternalProduct
from app.models.platform_shop import PlatformShop
from langchain_core.tools import tool


class ProductAgent(BaseExpertAgent):
    name = "product"
    description = "商品语义搜索、库存查询、商品推荐"

    def _build_tools(self) -> list:
        mid = self.merchant_id

        @tool
        def search_product_kb(query: str) -> str:
            """语义搜索商品。query 为商品关键词或买家问题。返回匹配商品的标题、价格、评分。"""
            try:
                from app.services.ai_suggest import semantic_search_products
                results = semantic_search_products(mid, query, shop_ids=[], top_k=5)
                if not results: return "未找到相关商品"
                lines = [f"商品:{r['title']} 价格:¥{r.get('price',0)} 评分:{r.get('score',0)}" for r in results]
                return "\n".join(lines)
            except Exception as e:
                return f"搜索失败: {e}"

        @tool
        def check_inventory(product_id: int) -> str:
            """查询商品库存。product_id 为数字ID。返回标题、库存、状态。"""
            db = SessionLocal()
            try:
                sids = [r[0] for r in db.query(PlatformShop.id).filter(PlatformShop.merchant_id == mid).all()]
                p = db.query(ExternalProduct).filter(ExternalProduct.id == product_id, ExternalProduct.shop_id.in_(sids)).first() if sids else None
                if not p: return f"商品{product_id}不存在"
                return f"商品:{p.title} 库存:{p.stock}件 状态:{'在售' if p.status==1 else '下架'} 价格:¥{float(p.price):.2f}"
            finally:
                db.close()

        @tool
        def get_hot_products(top_k: int = 5) -> str:
            """获取热销商品排行。"""
            try:
                from app.services.recommendation import recommend_hot
                results = recommend_hot(mid) if hasattr(recommend_hot := None, '__call__') else []
                if not results:
                    from app.database.session import SessionLocal
                    db = SessionLocal()
                    sids = [r[0] for r in db.query(PlatformShop.id).filter(PlatformShop.merchant_id == mid).all()]
                    prods = db.query(ExternalProduct).filter(ExternalProduct.shop_id.in_(sids)).order_by(ExternalProduct.stock.desc()).limit(top_k).all() if sids else []
                    db.close()
                    return "\n".join(f"商品:{p.title} 价格:¥{float(p.price):.2f} 库存:{p.stock}" for p in prods) if prods else "暂无推荐"
                return str(results)[:500]
            except Exception as e:
                return f"获取失败: {e}"

        return [search_product_kb, check_inventory, get_hot_products]

    def _build_prompt(self) -> str:
        return f"""你是商品专家。你可以搜索商品、查库存、推荐热销商品。
{self.role_prompt}
规则：必须调用工具。回复简洁（<200字）。"""
