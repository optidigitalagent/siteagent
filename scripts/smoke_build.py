from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from site_agent.builder import SiteBuilder
from site_agent.models import ResearchBrief, SectionSpec, SiteSpec, StrategyBrief


def main() -> None:
    research = ResearchBrief(
        instagram_url="https://www.instagram.com/example/",
        business_name="Studio Example",
        city="Tel Aviv",
        primary_language="ru",
        niche="салон красоты",
        services_or_products=["стрижки", "окрашивание", "уход"],
    )
    strategy = StrategyBrief(
        target_customer="Клиенты, которым нужен аккуратный результат и понятная консультация.",
        reason_to_choose=["Честная коммуникация", "Портфолио работ"],
        customer_questions_or_fears=["Сколько стоит", "Как записаться"],
        niche_specific_sections=["услуги", "портфолио", "запись"],
        primary_cta="Записаться в Instagram",
        secondary_cta="Посмотреть услуги",
        tone="спокойный, конкретный",
        color_direction="теплая нейтральная база с глубоким акцентом",
        typography_direction="контрастная editorial heading + нейтральный sans",
        business_logic="Сначала показать услугу и стиль, затем упростить запись.",
    )
    spec = SiteSpec(
        language="ru",
        title="Studio Example",
        meta_description="Салон красоты: стрижки, окрашивание и уход. Запись через Instagram.",
        h1="Стрижки, цвет и уход без лишнего шума",
        hero_subtitle="Запись на процедуры в салоне с акцентом на аккуратный результат и понятную консультацию перед визитом.",
        primary_cta="Записаться в Instagram",
        secondary_cta="Посмотреть услуги",
        sections=[
            SectionSpec(
                id="services",
                title="Услуги",
                purpose="Основные направления, видимые из профиля.",
                content=[
                    "Стрижки и форма с учетом привычной укладки.",
                    "Окрашивание и уход после консультации.",
                    "Актуальные цены лучше уточнить в Direct.",
                ],
                cta="Уточнить свободное время",
            )
        ],
        trust_points=[
            "Сайт не показывает выдуманные рейтинги или отзывы.",
            "Запись идет через официальный Instagram профиля.",
        ],
        process_steps=[
            "Откройте Instagram профиля.",
            "Напишите в Direct желаемую услугу и удобное время.",
            "Уточните цену и подготовку перед визитом.",
        ],
        contact_lines=["Instagram: https://www.instagram.com/example/"],
        footer_note="Для актуальных цен и свободного времени напишите в Instagram.",
        no_fake_claims_checklist=["Нет фейковых отзывов", "Нет неподтвержденных цен"],
    )
    SiteBuilder().build(
        site_dir=Path("runs/smoke/site"),
        research=research,
        strategy=strategy,
        spec=spec,
    )


if __name__ == "__main__":
    main()
