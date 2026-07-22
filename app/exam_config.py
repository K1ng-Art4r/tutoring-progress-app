from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GradeBand:
    grade: int
    minimum: float
    maximum: float
    label: str


@dataclass(frozen=True)
class ExamCompetency:
    key: str
    title: str
    description: str
    task_lines: tuple[int, ...]
    weight: int
    is_geometry: bool = False


@dataclass(frozen=True)
class ExamConfig:
    id: str
    title: str
    short_title: str
    subject: str
    exam_type: str
    max_primary_score: int
    competencies: tuple[ExamCompetency, ...]
    grade_bands: tuple[GradeBand, ...]
    chart_ticks: tuple[int, ...]
    chart_zones: tuple[tuple[int, int, int], ...]
    has_geometry_threshold: bool = False
    max_test_score: int | None = None
    exam_year: int | None = None
    primary_to_test: tuple[int, ...] = ()
    chart_max_score: int | None = None


OGE_COMPETENCIES = (
    ExamCompetency("practical", "Практико-ориентированные задачи", "Практические задачи первой части.", (1, 2, 3, 4, 5), 5),
    ExamCompetency("numbers_formulas", "Числа, выражения и формулы", "Вычисления и преобразования.", (6, 7, 8), 3),
    ExamCompetency("number_line", "Координаты на прямой", "Числа и координатная прямая.", (7,), 1),
    ExamCompetency("equations", "Уравнения", "Решение уравнений.", (6,), 1),
    ExamCompetency("probability_statistics", "Вероятность и статистика", "Вероятность и статистика.", (10,), 1),
    ExamCompetency("functions_graphs", "Функции и чтение графиков", "Функции и графики.", (9,), 1),
    ExamCompetency("inequalities_systems", "Неравенства и системы", "Неравенства и системы.", (11,), 1),
    ExamCompetency("sequences_progressions", "Последовательности и прогрессии", "Последовательности.", (12,), 1),
    ExamCompetency("geometry_first", "Геометрия первой части", "Геометрия первой части.", (7, 8), 5, True),
    ExamCompetency("algebra_second", "Алгебра второй части", "Алгебра второй части.", (), 2),
    ExamCompetency("word_problem_second", "Текстовая задача второй части", "Текстовая задача второй части.", (10,), 2),
    ExamCompetency("graphs_second", "Графики второй части", "Графики второй части.", (), 2),
    ExamCompetency("geometry_second_compute", "Геометрия второй части: вычисление", "Вычислительная геометрия.", (12,), 2, True),
    ExamCompetency("geometry_second_proof", "Геометрия второй части: доказательство", "Геометрическое доказательство.", (), 2, True),
    ExamCompetency("geometry_second_hard", "Геометрия второй части: сложная задача", "Сложная геометрия.", (), 2, True),
)


EGE_BASE_COMPETENCIES = (
    ExamCompetency("practical_calculations_rounding", "Практические расчёты и округление", "Покупки, тарифы, стоимость, количество предметов и реалистичное округление результата.", (1,), 1),
    ExamCompetency("text_problems_units_estimation", "Текстовые задачи и оценка результата", "Понимание условия, перевод величин, единицы измерения и проверка правдоподобности ответа.", (2,), 1),
    ExamCompetency("tables_charts_graphs", "Таблицы, диаграммы и графики", "Поиск, сравнение и анализ информации в таблицах, диаграммах и графиках.", (3, 6), 2),
    ExamCompetency("formulas_dependencies_calculations", "Формулы и зависимости", "Подстановка данных в формулу и последовательное выполнение вычислений.", (4,), 1),
    ExamCompetency("basic_probability", "Вероятность", "Вычисление вероятности простого случайного события.", (5,), 1),
    ExamCompetency("functions_graphs_derivative", "Функции, графики и производная", "Чтение графика функции, анализ поведения функции и смысл производной.", (7,), 1),
    ExamCompetency("logical_reasoning", "Логические рассуждения", "Проверка утверждений, причинно-следственные связи и выбор верных выводов.", (8,), 1),
    ExamCompetency("planimetry", "Геометрия на плоскости", "Длины, углы, площади, треугольники, четырёхугольники и окружности.", (9, 10, 12), 3, True),
    ExamCompetency("stereometry", "Объёмные фигуры", "Объёмы, площади поверхностей и пространственные фигуры.", (11, 13), 2, True),
    ExamCompetency("arithmetic_fractions_decimals", "Арифметика и дроби", "Порядок действий, обыкновенные и десятичные дроби, вычисления без калькулятора.", (14,), 1),
    ExamCompetency("percentages_financial_math", "Проценты и финансовые расчёты", "Проценты, скидки, наценки и изменение величины.", (15,), 1),
    ExamCompetency("powers_roots_logs_trigonometry", "Степени, корни, логарифмы и тригонометрия", "Вычисление выражений со степенями, корнями, логарифмами и тригонометрией.", (16,), 1),
    ExamCompetency("equations", "Уравнения", "Рациональные, иррациональные, показательные, тригонометрические и логарифмические уравнения.", (17,), 1),
    ExamCompetency("inequalities", "Неравенства", "Рациональные, показательные и логарифмические неравенства.", (18,), 1),
    ExamCompetency("number_properties_method_selection", "Свойства чисел и подбор решения", "Делимость, свойства целых чисел, перебор и выбор способа решения.", (19,), 1),
    ExamCompetency("word_problems_equations", "Сложные текстовые задачи", "Математическая модель, уравнение и проверка результата.", (20,), 1),
    ExamCompetency("nonstandard_logic_modeling", "Нестандартные задачи", "Анализ условий, перебор вариантов и поиск закономерности.", (21,), 1),
)


EGE_PROFILE_COMPETENCIES = (
    ExamCompetency("profile_planimetry_basic", "Планиметрия, базовая задача", "Базовая задача по геометрии на плоскости.", (1,), 1, True),
    ExamCompetency("profile_vectors", "Векторы", "Координаты, длина, скалярное произведение и операции с векторами.", (2,), 1),
    ExamCompetency("profile_stereometry_basic", "Стереометрия, базовая задача", "Базовая задача по пространственной геометрии.", (3,), 1, True),
    ExamCompetency("profile_probability_simple", "Простая вероятность", "Вероятность простого случайного события.", (4,), 1),
    ExamCompetency("profile_probability_advanced", "Сложная вероятность и комбинаторика", "Условная вероятность, комбинации событий и подсчёт вариантов.", (5,), 1),
    ExamCompetency("profile_equations_short", "Уравнения с кратким ответом", "Решение уравнения экзаменационного формата с кратким ответом.", (6,), 1),
    ExamCompetency("profile_transformations", "Степени, корни, логарифмы и преобразования", "Преобразование алгебраических выражений.", (7,), 1),
    ExamCompetency("profile_derivative_graph", "Производная, первообразная и чтение графика", "Смысл производной, первообразная и анализ графика.", (8,), 1),
    ExamCompetency("profile_applied_formula", "Прикладная задача и работа с формулами", "Подстановка в формулу и прикладные вычисления.", (9,), 1),
    ExamCompetency("profile_word_problems", "Текстовые задачи", "Математическая модель задачи на движение, работу или смеси.", (10,), 1),
    ExamCompetency("profile_functions_graphs", "Функции и графики", "Свойства функций и чтение графиков.", (11,), 1),
    ExamCompetency("profile_extrema", "Экстремумы функции", "Поиск наибольшего и наименьшего значения функции.", (12,), 1),
    ExamCompetency("profile_equation_detailed", "Сложное уравнение и отбор корней", "Решение сложного уравнения и корректный отбор корней.", (13,), 2),
    ExamCompetency("profile_stereometry_detailed", "Стереометрия с развёрнутым решением", "Доказательная и вычислительная части стереометрической задачи.", (14,), 3, True),
    ExamCompetency("profile_inequalities", "Неравенства", "Решение сложного неравенства с обоснованием.", (15,), 2),
    ExamCompetency("profile_finance", "Финансовая и экономическая задача", "Кредиты, вклады и экономические модели.", (16,), 2),
    ExamCompetency("profile_planimetry_proof", "Планиметрия с доказательством", "Доказательство и вычислительная часть планиметрической задачи.", (17,), 3, True),
    ExamCompetency("profile_parameter", "Задача с параметром", "Анализ случаев и полный ответ в задаче с параметром.", (18,), 4),
    ExamCompetency("profile_number_theory", "Теория чисел и доказательная задача", "Делимость, целые числа и доказательные рассуждения.", (19,), 4),
)


EGE_PROFILE_PRIMARY_TO_TEST = (
    0, 6, 11, 17, 22, 27, 34, 40, 46, 52, 58,
    64, 70, 72, 74, 76, 78, 80, 82, 84, 86, 88,
    90, 92, 94, 95, 96, 97, 98, 99, 100, 100, 100,
)


OGE_CONFIG = ExamConfig(
    id="oge_math",
    title="ОГЭ по математике",
    short_title="Математика, ОГЭ",
    subject="Математика, ОГЭ",
    exam_type="ОГЭ",
    max_primary_score=31,
    competencies=OGE_COMPETENCIES,
    grade_bands=(
        GradeBand(2, 0, 7.999, "Зона риска"),
        GradeBand(3, 8, 14.999, "Сдача уже видна, но нестабильно"),
        GradeBand(4, 15, 21.999, "Рабочая оценка 4"),
        GradeBand(5, 22, 31, "Зона оценки 5"),
    ),
    chart_ticks=(0, 8, 15, 22, 31),
    chart_zones=((5, 22, 31), (4, 15, 22), (3, 8, 15), (2, 0, 8)),
    has_geometry_threshold=True,
)


EGE_BASE_CONFIG = ExamConfig(
    id="ege_base_math",
    title="ЕГЭ по математике, базовый уровень",
    short_title="Математика, ЕГЭ база",
    subject="Математика, ЕГЭ база",
    exam_type="ЕГЭ база",
    max_primary_score=21,
    competencies=EGE_BASE_COMPETENCIES,
    grade_bands=(
        GradeBand(2, 0, 6.999, "Экзамен пока не сдан"),
        GradeBand(3, 7, 11.999, "Экзамен сдан"),
        GradeBand(4, 12, 16.999, "Хороший результат"),
        GradeBand(5, 17, 21, "Отличный результат"),
    ),
    chart_ticks=(0, 7, 12, 17, 21),
    chart_zones=((5, 17, 21), (4, 12, 17), (3, 7, 12), (2, 0, 7)),
)


EGE_PROFILE_CONFIG = ExamConfig(
    id="ege_profile_math",
    title="ЕГЭ по математике, профильный уровень",
    short_title="Математика, ЕГЭ профиль",
    subject="Математика, ЕГЭ профиль",
    exam_type="ЕГЭ профиль",
    max_primary_score=32,
    max_test_score=100,
    exam_year=2026,
    primary_to_test=EGE_PROFILE_PRIMARY_TO_TEST,
    competencies=EGE_PROFILE_COMPETENCIES,
    grade_bands=(),
    chart_ticks=(0, 27, 80, 100),
    chart_zones=((5, 80, 100), (4, 27, 80), (2, 0, 27)),
    chart_max_score=100,
)


EXAM_CONFIGS = (OGE_CONFIG, EGE_BASE_CONFIG, EGE_PROFILE_CONFIG)


def get_exam_config(subject: str) -> ExamConfig | None:
    normalized = subject.replace(" · демо", "").strip()
    for config in EXAM_CONFIGS:
        if normalized == config.subject:
            return config
    return None


def grade_for_score(config: ExamConfig, score: float) -> int:
    if not config.grade_bands:
        return 0
    bounded = min(max(float(score), 0.0), config.max_primary_score)
    for band in config.grade_bands:
        if band.minimum <= bounded <= band.maximum:
            return band.grade
    return config.grade_bands[-1].grade


def grade_label(config: ExamConfig, score: float) -> str:
    if not config.grade_bands:
        return "Тестовый балл"
    grade = grade_for_score(config, score)
    return next(band.label for band in config.grade_bands if band.grade == grade)


def ege_profile_test_score(primary_score: float) -> float:
    bounded = min(max(float(primary_score), 0.0), 32.0)
    lower = int(bounded)
    upper = min(lower + 1, 32)
    fraction = bounded - lower
    table = EGE_PROFILE_PRIMARY_TO_TEST
    return table[lower] + fraction * (table[upper] - table[lower])
