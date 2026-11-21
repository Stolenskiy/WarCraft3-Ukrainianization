"""Ukrainian translations for standard Warcraft III 1.31 melee maps.

Three tables:
  NAMES   — map display name, keyed by map file basename
  DESCS   — map description, keyed by the exact stripped English description
  PLAYERS — suggested-players string, keyed by exact stripped English string
"""

NAMES = {
    # --- Reign of Chaos melee maps (Maps/) ---
    "(1)thedeathsheep.w3m": "Вівця Смерті",
    "(10)dustwallowkeys.w3m": "Ключі Пилових Топей",
    "(12)divideandconquer.w3m": "Розділяй і Володарюй",
    "(12)icecrown.w3m": "Крижана Корона",
    "(2)bootybay.w3m": "Затока Здобичі",
    "(2)harrow.w3m": "Борона",
    "(2)hillsofglory.w3m": "Пагорби Слави",
    "(2)ogremound.w3m": "Огровий Курган",
    "(2)plunderisle.w3m": "Острів Грабунку",
    "(3)forestwalk.w3m": "Лісова Тропа",
    "(3)isleofdread.w3m": "Острів Жаху",
    "(3)nighthaven.w3m": "Нічна Гавань",
    "(4)adrenaline.w3m": "Адреналін",
    "(4)borderlands.w3m": "Прикордоння",
    "(4)deadlock.w3m": "Тупик",
    "(4)deadwaterdrop.w3m": "Водоспад Мертвої Води",
    "(4)dragonmountain.w3m": "Драконяча Гора",
    "(4)duskwood.w3m": "Сутінковий Ліс",
    "(4)frostsabre.w3m": "Крижана Шабля",
    "(4)harvestmoon.w3m": "Місяць Жнив",
    "(4)hearttoheart.w3m": "Серце до Серця",
    "(4)legends.w3m": "Легенди",
    "(4)losttemple.w3m": "Загублений Храм",
    "(4)mysticisles.w3m": "Містичні Острови",
    "(4)tranquilpaths.w3m": "Спокійні Стежки",
    "(4)warchasers.w3m": "Мисливці за Війною",
    "(5)theglaive.w3m": "Глефа",
    "(6)darkforest.w3m": "Темний Ліс",
    "(6)dragonfire.w3m": "Драконяче Полум'я",
    "(6)drywatergulch.w3m": "Сухий Яр",
    "(6)gnollwood.w3m": "Ліс Гнолів",
    "(6)moonglade.w3m": "Місячна Поляна",
    "(6)scorchedbasin.w3m": "Випалена Улоговина",
    "(6)stromguarde.w3m": "Стромгард",
    "(6)swampofsorrows.w3m": "Болото Скорботи",
    "(6)timbermawhold.w3m": "Твердиня Деревопащі",
    "(8)battleground.w3m": "Поле Битви",
    "(8)blastedlands.w3m": "Спалені Землі",
    "(8)bloodvenomfalls.w3m": "Водоспад Кривавої Отрути",
    "(8)gardenofwar.w3m": "Сад Війни",
    "(8)golemsinthemist.w3m": "Големи в Імлі",
    "(8)petrifiedforest.w3m": "Окам'янілий Ліс",
    "(8)plaguelands.w3m": "Чумні Землі",
    "(8)plainsofsnow.w3m": "Сніжні Рівнини",
    "(8)richmansgarden.w3m": "Сад Багатія",
    "(8)thecrucible.w3m": "Тигель",
    "(9)riverrun.w3m": "Заплава",
    # --- Frozen Throne melee maps (Maps/FrozenThrone/) ---
    "(10)extremecandywar2004.w3x": "|cffffaa00Крайня Цукрова Війна 2004|r",
    "(10)extremecandywar2005.w3x": "|cffffaa00Крайня Цукрова Війна 2005|r",
    "(10)ragingstream.w3x": "Шалений Потік",
    "(10)skibi'scastletd.w3x": "|cff80ff80Замок Скібі TD ",
    "(12)emeraldgardens.w3x": "Смарагдові Сади",
    "(12)wormwar.w3x": "Війна Хробаків",
    "(2)amazonia.w3x": "Амазонія",
    "(2)ancientisles.w3x": "Стародавні Острови",
    "(2)banditridge.w3x": "Розбійницький Кряж",
    "(2)circumvention.w3x": "Обхідний Шлях",
    "(2)concealedhill.w3x": "Прихований Пагорб",
    "(2)echoisles.w3x": "Острови Луна",
    "(2)glacialthaw.w3x": "Крижана Відлига",
    "(2)justice.w3x": "Правосуддя",
    "(2)korea.w3x": "Корея",
    "(2)lastrefuge.w3x": "Останній Притулок",
    "(2)meltingvalley.w3x": "Таюча Долина",
    "(2)northernisles.w3x": "Північні Острови",
    "(2)plunderisle_lv.w3x": "Острів Грабунку LV",
    "(2)roadtostratholme.w3x": "Шлях до Стратхольма",
    "(2)roadtostratholme_lv.w3x": "Шлях до Стратхольма LV",
    "(2)secretvalley.w3x": "Таємна Долина",
    "(2)shrineoftheancients.w3x": "Святилище Давніх",
    "(2)swampedtemple.w3x": "Затоплений Храм",
    "(2)terenasstand.w3x": "Постамент Терени",
    "(2)terenasstand_lv.w3x": "Постамент Терени LV",
    "(2)thetworivers.w3x": "Дві Ріки",
    "(2)thetworivers_lv.w3x": "Дві Ріки LV",
    "(2)tirisfalglades.w3x": "Ліс Тірісфаль",
    "(2)tirisfalglades_lv.w3x": "Ліс Тірісфаль LV",
    "(3)nomadisles.w3x": "Кочові Острови",
    "(4)adrenaline.w3x": "Адреналін",
    "(4)avalanche.w3x": "Лавина",
    "(4)avalanche_lv.w3x": "Лавина LV",
    "(4)bridgetoonear.w3x": "Міст Надто Близько",
    "(4)bridgetoonear_lv.w3x": "Міст Надто Близько LV",
    "(4)brokenshard.w3x": "Розбитий Уламок",
    "(4)brutalwinter.w3x": "Люта Зима",
    "(4)centaurgrove.w3x": "Кентаврський Гай",
    "(4)coldheart.w3x": "Холодне Серце",
    "(4)deadfall.w3x": "Силок",
    "(4)deathrose.w3x": "Троянда Смерті",
    "(4)desertstrife.w3x": "Пустельна Смута",
    "(4)devilscauldron.w3x": "Котол Диявола",
    "(4)duskwood_lv.w3x": "Сутінковий Ліс LV",
    "(4)excavationsite.w3x": "Місце Розкопок",
    "(4)floodplains.w3x": "Заплави",
    "(4)floodplains1v1.w3x": "Заплави 1v1",
    "(4)floodplains1v1_lv.w3x": "Заплави 1v1 LV",
    "(4)fountainofmanipulation.w3x": "Фонтан Маніпуляцій",
    "(4)frozenclover.w3x": "Крижана Конюшина",
    "(4)frozenclover_lv.w3x": "Крижана Конюшина LV",
    "(4)furbolgmountain.w3x": "Гора Фурболгів",
    "(4)goldshire.w3x": "Златозілля",
    "(4)hailstone.w3x": "Градовиця",
    "(4)hearthglenhills.w3x": "Пагорби Герстґлену",
    "(4)hellfire.w3x": "Пекельне Полум'я",
    "(4)iceflow.w3x": "Крижаний Плин",
    "(4)iceforge.w3x": "Крижана Кузня",
    "(4)islands.w3x": "Острови",
    "(4)losttemple.w3x": "Загублений Храм",
    "(4)monolith.w3x": "Моноліт",
    "(4)paradiseislands.w3x": "Райські Острови",
    "(4)phantomgrove.w3x": "Примарний Гай",
    "(4)phantomgrove_lv.w3x": "Примарний Гай LV",
    "(4)predators.w3x": "Хижаки",
    "(4)roundabout.w3x": "Об'їзд",
    "(4)ruins.w3x": "Руїни",
    "(4)stonecoldmountain.w3x": "Гора Кам'яного Холоду",
    "(4)synergybigpaved.w3x": "Синергія",
    "(4)tanaris.w3x": "Танаріс",
    "(4)tidewaterglades.w3x": "Приливні Гаї",
    "(4)tidewaterglades_lv.w3x": "Приливні Гаї LV",
    "(4)turtlerock.w3x": "Скеля Черепахи",
    "(4)twistedmeadows.w3x": "Викривлені Луки",
    "(4)venetia.w3x": "Венеція",
    "(4)wetlands.w3x": "Вологі Рівнини",
    "(4)whirlwind.w3x": "Вихор",
    "(4)windywaste.w3x": "Вітряна Пустка",
    "(6)andorhal.w3x": "Андорал",
    "(6)blizzardtd.w3x": "Баштова Оборона Blizzard",
    "(6)bloodstonemesa.w3x": "Плато Кривавого Каменю",
    "(6)bombercommand.w3x": "Командування Бомбардувальників",
    "(6)coppercanyon.w3x": "Мідний Каньйон",
    "(6)demon'scrossing.w3x": "Переправа Демонів",
    "(6)dragonblight.w3x": "Драконяча Пустош",
    "(6)duststorm.w3x": "Пилова Буря",
    "(6)duststorm_lv.w3x": "Пилова Буря LV",
    "(6)emeraldshores.w3x": "Смарагдові Береги",
    "(6)enakrosway.w3x": "Шлях Енакро",
    "(6)everfrost.w3x": "Вічна Мерзлота",
    "(6)gnollwood.w3x": "Ліс Гнолів",
    "(6)havenofthedamned.w3x": "Притулок Проклятих",
    "(6)highperch.w3x": "Високий Виступ",
    "(6)hinterlandraid.w3x": "Рейд у Глибинні Землі",
    "(6)jack-o-lantern.w3x": "Гарбуз-Ліхтар",
    "(6)junglefever.w3x": "Гарячка Джунглів",
    "(6)monsoon.w3x": "Мусон",
    "(6)monsoon_lv.w3x": "Мусон LV",
    "(6)moonglade.w3x": "Місячна Поляна",
    "(6)neoncity.w3x": "Неонове Місто",
    "(6)ricefields.w3x": "Рисові Поля",
    "(6)riverofsouls.w3x": "Ріка Душ",
    "(6)rollinghills.w3x": "Хвилясті Пагорби",
    "(6)ruinsofstratholme.w3x": "Руїни Стратхольма",
    "(6)savagestorm.w3x": "Дика Буря",
    "(6)scorchedbasin.w3x": "Випалена Улоговина",
    "(6)silverpineforest.w3x": "Срібний Бір",
    "(6)stranglethornvale.w3x": "Терниста Долина",
    "(6)sunrockcove.w3x": "Бухта Сонячної Скелі",
    "(6)thunderlake.w3x": "Громове Озеро",
    "(6)thunderlake_lv.w3x": "Громове Озеро LV",
    "(6)timbermawhold.w3x": "Твердиня Деревопащі",
    "(6)typhoon.w3x": "Тайфун",
    "(6)upperkingdom.w3x": "Верхнє Королівство",
    "(6)wellspring.w3x": "Джерело",
    "(6)wheelofchaos.w3x": "Колесо Хаосу",
    "(6)wizardsretreat.w3x": "Притулок Чарівників",
    "(8)azerothgrandprix.w3x": "Гран-прі Азероту",
    "(8)azuretowerdefense.w3x": "Лазурна Оборона Веж",
    "(8)banewoodbog.w3x": "Болото Згубного Бору",
    "(8)battleground.w3x": "Поле Битви",
    "(8)battleground_lv.w3x": "Поле Битви LV",
    "(8)cherryville.w3x": "Вишневиця",
    "(8)deadlands.w3x": "Мертві Землі",
    "(8)deadlock.w3x": "Тупик",
    "(8)deadlock_lv.w3x": "Тупик LV",
    "(8)deathknell.w3x": "Смертний Дзвін",
    "(8)dragonfalls.w3x": "Драконячі Водоспади",
    "(8)feralas.w3x": "Фералас",
    "(8)feralas_lv.w3x": "Фералас LV",
    "(8)friends.w3x": "Друзі",
    "(8)fullscaleassault.w3x": "Штурм Усіма Силами",
    "(8)funnybunnysegghunt.w3x": "Веселе Полювання на Яйця",
    "(8)gardenofwar.w3x": "Сад Війни",
    "(8)goldrush.w3x": "Золота Лихоманка",
    "(8)golemsinthemist_lv.w3x": "Големи в Імлі LV",
    "(8)hurricaneisle.w3x": "Острів Ураганів",
    "(8)lastmanstanding.w3x": "Останній Герой",
    "(8)marketsquare.w3x": "Ринкова Площа",
    "(8)mur'guloasis.w3x": "Оаза Мургулів",
    "(8)mur'guloasis_lv.w3x": "Оаза Мургулів LV",
    "(8)nerubianpassage.w3x": "Неруб'янський Перехід",
    "(8)northshire.w3x": "Нортшир",
    "(8)northshire_lv.w3x": "Нортшир LV",
    "(8)plainsofsnow.w3x": "Сніжні Рівнини",
    "(8)rockquarry.w3x": "Каменярня",
    "(8)sanctuary.w3x": "Убежище",
    "(8)sanctuary_lv.w3x": "Убежище LV",
    "(8)shamrockreef.w3x": "Риф Трилисника",
    "(8)slalom.w3x": "Слалом",
    "(8)spiderfalls.w3x": "Павучі Водоспади",
    "(8)thecrossroads.w3x": "Перехрестя",
    "(8)twilightruins.w3x": "Сутінкові Руїни",
    "(8)twilightruins_lv.w3x": "Сутінкові Руїни LV",
    "(9)roundvillage.w3x": "Кругле Село",
}

# English players string -> Ukrainian
PLAYERS = {
    "1": "1",
    "4": "4",
    "1v1": "1v1",
    "2v2": "2v2",
    "4v4, 5v5": "4v4, 5v5",
    "4v4 or 5v5": "4v4 або 5v5",
    "3v3v3v3 or 6v6": "3v3v3v3 або 6v6",
    "3v3 or 3v3v3": "3v3 або 3v3v3",
    "FFA": "Кожен за себе",
    "FFA or 2v2": "Кожен за себе або 2v2",
    "FFA or 4v4": "Кожен за себе або 4v4",
    "FFA or 2v2 - 3v3": "Кожен за себе або 2v2 – 3v3",
    "FFA or 2v2 - 4v4": "Кожен за себе або 2v2 – 4v4",
    "FFA, 2v2 or 4v4": "Кожен за себе, 2v2 або 4v4",
    "FFA, 2v2 or 3v3": "Кожен за себе, 2v2 або 3v3",
    "FFA, 3v3 or 4v4": "Кожен за себе, 3v3 або 4v4",
    "FFA, 2v2v2, 3v3": "Кожен за себе, 2v2v2, 3v3",
    "1v1, 2v2, or FFA": "1v1, 2v2 або кожен за себе",
    "1v1, 2v2": "1v1, 2v2",
    "1v1 or 2v2": "1v1 або 2v2",
    "2v2 or FFA": "2v2 або кожен за себе",
    "2v2 or 3v3": "2v2 або 3v3",
    "2v2 or 4v4": "2v2 або 4v4",
    "2v2, 3v3, or FFA": "2v2, 3v3 або кожен за себе",
    "2v2, 4v4, or FFA": "2v2, 4v4 або кожен за себе",
    "3v3 or 4v4": "3v3 або 4v4",
    "3v3, 4v4, or FFA": "3v3, 4v4 або кожен за себе",
    "3v3 or 4v4 ": "3v3 або 4v4",
    "2v2 - 4v4 or FFA": "2v2 – 4v4 або кожен за себе",
    "2v2 - 3v3 or FFA": "2v2 – 3v3 або кожен за себе",
    "2v2 - 3v3 ": "2v2 – 3v3",
    "1v1 - 3v3 or FFA": "1v1 – 3v3 або кожен за себе",
    "1v1- 3v3 or FFA": "1v1 – 3v3 або кожен за себе",
    "2v2v2v2 or 4v4": "2v2v2v2 або 4v4",
    "3v3v3, 2v2 - 3v3": "3v3v3, 2v2 – 3v3",
    "2v2 or 3v3 ": "2v2 або 3v3",
    "1v1, 2v2, or FFA ": "1v1, 2v2 або кожен за себе",
    "4 or 8": "4 або 8",
    "4 to 8": "4–8",
    "1 to 6": "1–6",
    "1-10": "1–10",
    "4-12": "4–12",
    "1-4 (Co-op Play)": "1–4 (спільна гра)",
    "4 ": "4",
    "2v2 ": "2v2",
    "1v1, 2v2 ": "1v1, 2v2",
    "3v3 ": "3v3",
}

DESCS = {
    "Avoid the sheep! \r\n\r\nUse S to move left, H to move right, and ESC to execute a special move.":
        "Уникай вівці!\r\n\r\nКерування: S — вліво, H — вправо, ESC — особливий прийом.",
    "The sands are rich with gold, but all of it is under Centaur control. This region is densely populated; be prepared for a bloody struggle.":
        "Піски багаті на золото, але все воно в руках кентаврів. Регіон густо заселений, тож готуйтеся до кривавої боротьби.",
    "Trolls and Golems control this beautiful forest. Expand quickly, and stain the river with the blood of your enemies.":
        "Цим прекрасним лісом володіють тролі та големи. Розширюйтеся швидко й зафарбуйте річку кров'ю своїх ворогів.",
    "These frozen woods are haunted by souls in torment, enslaved by the dark magic of the Undead. End their suffering.":
        "Цими крижаними лісами блукають катовані душі, закуті в темну магію нежиті. Покладіть край їхнім стражданням.",
    "Pirates once anchored their ships in these quiet coves. Now the area is overrun with more brutal tenants. Establish your own kingdom on these islands before your opponent does.":
        "Колись пірати кидали якір у цих тихих затоках. Тепер тут панують набагато жорстокіші господарі. Заснуйте власне королівство на цих островах, поки цього не зробив ваш суперник.",
    "The first snowfall has come, and resources are limited. There's no time to waste.":
        "Випав перший сніг, а ресурсів обмаль. Гаяти час не доводиться.",
    "Unsavory creatures inhabit these verdant hills. The coasts are guarded by a set of twin Red Dragons who discovered long ago that the incoming ships made delicious and regular meals.":
        "У цих пишних пагорбах мешкають огидні створіння. Узбережжя охороняє пара червоних драконів, які давно збагнули, що кораблі, що заходять у затоку, — смачна й регулярна пожива.",
    "These islands are rich with gold, but the treasure is controlled by Ogres.":
        "Ці острови багаті на золото, але скарбами володіють огри.",
    "So far the Ogres have managed to hold off the Gnolls and hoard the richest resources. Crush both their races, as well as your opponent, beneath your heel.":
        "Досі огри стримують гнолів і тримають за собою найбагатші ресурси. Роздавіть обидва ці народи — і свого суперника — під своєю п'ятою.",
    "Ragged cobwebs hang from the trees; clearly Spiders are the dominant race here. Demon bile has scarred the earth and twisted these creatures almost beyond recognition.":
        "З гілок звисають обірвані павутиння; очевидно, панівний народ тут — павуки. Демонічна жовч випалила землю, а самих тварин спотворила майже до невпізнанності.",
    "Having allied with a trio of Bronze Dragons, the Centaur are the uncontested rulers of this island. Build up a reasonable force before you pick a fight.":
        "Заручившись підтримкою трьох бронзових драконів, кентаври стали беззаперечними володарями цього острова. Зберіть пристойне військо, перш ніж шукати бійки.",
    "Once a temple dedicated to light and life, this area is now a swamp littered with rocks and thorny vines. The air is thick with the miasma of disease. Raze the trees to reach your opponents.":
        "Колись тут стояв храм, присвячений світлу й життю, тепер же це болото, всіяне камінням і колючими лозами. Повітря густе від смороду хвороби. Викорчуйте дерева, щоб дістати своїх суперників.",
    "Hack your way through the trees to expand and get at your opponents, but be wary. Rumor has it that in ages past, a Red Dragon made this land her home.":
        "Пробивайте собі шлях крізь дерева, щоб розширюватися й діставати суперників, але будьте обережні. Ходять чутки, що колись у цих краях оселилася червона дракониця.",
    "This shadowed forest is thick with Dark Trolls, who make tasty treats for the powerful scaled beasts that hold the central hill. Level the trees to reach your enemies.":
        "Цей тінистий ліс густо заселений темними тролями, які стають смачним частуванням для могутніх лускатих звірів, що тримають центральний пагорб. Зрівняйте дерева із землею, щоб дістати ворогів.",
    "The easiest expansions to claim are often the most difficult to keep.":
        "Найлегші для захоплення розширення найчастіше найважче втримати.",
    "Gold is plentiful in this wooded place, but so is competition. Stake your claim to the sacred Fountain of the Nightcrawlers.":
        "У цьому лісовому краї золота вдосталь, але й конкуренції чимало. Заявіть права на священний Фонтан Земляних Хробаків.",
    "Dragons have laid claim to these hills. Team up to claim their treasure; otherwise, you won't stand a chance.":
        "Дракони захопили ці пагорби. Об'єднуйтеся, щоб забрати їхні скарби, — інакше у вас немає жодних шансів.",
    "The green of their scales is difficult to spot in the thick undergrowth, but don't underestimate the beasts that dominate this jungle. Be prepared for a fierce fight.":
        "Зелені луски важко помітити в густих заростях, та не недооцінюйте звірів, що панують у цих джунглях. Готуйтеся до запеклого бою.",
    "It's said this island's Dragons will offer their assistance to any bold enough to prove their worthiness. Its also rumored their breath is colder than the grave.":
        "Кажуть, дракони цього острова допоможуть кожному, хто наважиться довести свою гідність. А ще мовлять, начебто їхнє дихання холодніше за могилу.",
    "Expand quickly and fight your way to the center to defeat the Ogres and win vast wealth.":
        "Розширюйтеся швидко та пробивайтеся до центру, щоб розгромити огрів і здобути величезне багатство.",
    "An Orc warrior died here while protecting the woman he loved. Both their names have been forgotten, but the powerful magic of his sacrifice reshaped the land into a lasting tribute to her.":
        "Тут загинув воїн-орк, захищаючи кохану жінку. Імена обох забуто, але могутня магія його жертви переплавила цей край у вічний пам'ятник їй.",
    "Rich with resources and treasure, these forests would make an excellent foundation on which to build an empire.":
        "Багаті на ресурси та скарби, ці ліси стануть чудовим підґрунтям для зведення імперії.",
    "Ringed by gold mines, the Fountain of Health beckons. Expand quickly or risk being crushed by your opponents.":
        "Оточений золотими копальнями, Фонтан Здоров'я кличе до себе. Розширюйтеся швидко, інакше ризикуєте бути розчавленими суперниками.",
    "Time and the ocean have ravaged these islands. Soon even their magical Way Gates will be replaced by an expanse of endless blue.":
        "Час і океан спустошили ці острови. Скоро навіть їхні чарівні Брами Шляхів зникнуть під безкрайньою синявою.",
    "Disturb the tranquility of these lands at your own peril. Beyond the rivers lies great wealth.":
        "Порушуйте спокій цих земель на свій страх і ризик. За ріками ховається величезне багатство.",
    "Four daring souls embody an ancient hero and co-operatively fight their way through a legendary city against overwhelming masses of monsters!\r\n(Turn 'Subtitles' on)":
        "Чотири відчайдухи вселяються в давнього героя і спільно пробиваються крізь легендарне місто, повне незліченних чудовиськ!\r\n(Увімкніть «Субтитри»)",
    "Only one intrepid Goblin Merchant has ever dared to set up business on this island, and business hasn't been so good since a group of Dragons decided he had a choice location.":
        "Лише один відчайдушний гоблін-торгаш наважився колись відкрити справу на цьому острові, та з часом справа пішла кепсько — відколи група драконів вирішила, що він зайняв надто вдале місце.",
    "Drive the invaders from these ancient lands. Be wary of the soulless guardians of stone; their treasure troves could turn the tide of war.":
        "Вигоніть загарбників із цих давніх земель. Стережіться бездушних кам'яних вартових: їхні скарбниці можуть переломити хід війни.",
    "It's unseasonably warm for autumn, and the stench of sulfur is in the air. Clearly Dragons inhabit these dusty plains.":
        "Осінь стоїть незвично тепло, а в повітрі витає сморід сірки. Безсумнівно, на цих припилених рівнинах живуть дракони.",
    "Lightning flashes nearby, but the sky is cloudless. The harsh sun and barren landscape have toughened this land's residents into formidable opponents.":
        "Поруч спалахує блискавка, та небо безхмарне. Люте сонце й безплідний край загартували мешканців цих земель у грізних суперників.",
    "Prepare your defenses quickly; the enemy draws near. Be careful when scouting the river's edge; Golems are lurking in the hills.":
        "Швидко зведіть оборону — ворог уже близько. Обережно розвідуйте береги річки: у пагорбах підстерігають големи.",
    "So far untouched by the Legion's corruption, these marshlands are inhabited by a tribe of Furbolgs who do not welcome interlopers.":
        "Досі не зачеплені скверною Легіону, ці болотисті землі населені плем'ям фурболгів, які не раді чужинцям.",
    "As vicious as they are lovely, Harpies have begun moving onto these sands, vying with the Centaur and Razormanes for resources.":
        "Вправні у жорстокості, як і у своїй вроді, гарпії почали осідати на цих пісках, змагаючись із кентаврами та бритвенцями за ресурси.",
    "This city is controlled by a pack of Bandits and Wizards. Entering it at night could be fatal if you don't keep your eyes open.":
        "Цим містом керує зграя розбійників і чарівників. Нічний вхід може виявитися смертельним, якщо не тримати очі відкритими.",
    "A tribe of Furbolgs is stubbornly holding its own against the foul creatures invading this swamp. It's unlikely they'll last much longer, though.":
        "Плем'я фурболгів вперто стримує навалу огидних створінь у цьому болоті. Хоча, схоже, протримаються вони недовго.",
    "Centuries ago, Dragons abandoned this place when it was overrun by Satyrs. Wade the shallows and reclaim the land.":
        "Століття тому дракони покинули це місце, коли його захопили сатири. Подолайте мілини й поверніть собі цю землю.",
    "The icy chill of winter has begun to fall on these war-torn lands. Gather what gold you can now, for the season of frost is fast approaching.":
        "На ці спустошені війною землі опускається крижаний подих зими. Збирайте золото, поки не пізно, — пора морозів насувається стрімко.",
    "The barrens are littered with gold mines and heavily populated with Centaur. Team up, and don't bother leaving your base until you're prepared for a bloody conflict.":
        "Пустоші всіяні золотими копальнями та густо заселені кентаврами. Об'єднуйтеся і не з'являйтеся поза базою, доки не будете готові до кривавої сутички.",
    "Darkness has invaded this swamp; even the Treants have been warped by its influence. You're going to need your allies' help.":
        "Це болото поглинула темрява; навіть дереволюдів спотворив її вплив. Без допомоги союзників вам не обійтися.",
    "Team up, or be ready for a serious challenge. Squads of hostile creatures have these woods in a stranglehold, and Ogres hoard the central gold mines.":
        "Об'єднуйтеся або готуйтеся до серйозного випробування. Ватаги ворожих створінь тримають ці ліси в смертельних обіймах, а центральні золоті копалини тримають огри.",
    "Ally with a partner to defeat your enemies. Both riches and danger await those who explore deep into the forest.":
        "Заручіться підтримкою союзника, щоб перемогти ворогів. І багатство, і небезпека чекають на тих, хто зайде глибоко в ліс.",
    "Satyrs have wiped out most of this island's residents so as to control its vast wealth. Only two Mercenary Camps still offer their services, and they haven't seen much profit lately.":
        "Сатири винищили більшість мешканців цього острова, щоб зосередити його величезні багатства в своїх руках. Лише два табори найманців ще пропонують свої послуги — та й ті останнім часом не бачать великих прибутків.",
    "Coordinate your attacks with your allies, or you'll stand little chance. Use the nearest Way Gates to scout your enemies before they find you.":
        "Координуйте свої атаки з союзниками, інакше шансів майже немає. Скористайтеся найближчими Брамами Шляхів, щоб розвідати ворогів, доки вони не знайшли вас.",
    "This arctic land is starkly beautiful, but merciless as well. It's unlikely anything could survive this brutal weather without a thick coat of fur--or the aid of magic.":
        "Цей арктичний край суворо-прекрасний, але й безжалісний. Навряд чи хтось виживе в таку люту погоду без густого хутра — або без допомоги магії.",
    "A very rich man owns these gardens.  Steal his money - if you can.":
        "Цими садами володіє дуже багата людина. Викрадіть його гроші — якщо зможете.",
    "Ready to prey on the unwary, Bandits lurk in the shadows. This rich forest shelters two Fountains that glow with magic.":
        "Розбійники, готові накинутися на необережних, ховаються в тіні. Цей багатий ліс приховує два Фонтани, що сяють магією.",
    "Seeking the Burning Legion's favor, Satyrs have secured most of the bridges on these islands. Dare to achieve what they did not.":
        "Прагнучи прихильності Палаючого Легіону, сатири захопили більшість мостів на цих островах. Наважтеся на те, що не змогли вони.",
    "Happy Halloween!":
        "Веселого Хелловіну!",
    "Updated version of Extreme Candy War for 2005. Happy Halloween!!":
        "Оновлена версія Крайньої Цукрової Війни для 2005 року. Веселого Хелловіну!",
    "This city is tightly packed with resources, but long ago, a flood killed most of its citizens. Coordinate with your allies, and be the first team to brave the rapids.":
        "Це місто щільно наповнене ресурсами, але колись повінь забрала життя більшості його мешканців. Координуйте дії з союзниками й станьте першою командою, що наважиться на пороги.",
    "Official Blizzard version of the popular TD with a mini-game twist! Defeat the onslaught of mobs solo or in two teams of up to five players each.":
        "Офіційна версія Blizzard популярної баштової оборони з мінігрою! Подолайте навалу монстрів поодинці або у двох командах до п'яти гравців у кожній.",
    "Lush greenery has almost succeeded in cloaking the ruins of a city whose name has passed into memory. Pay heed to its mute testimony: peace is fragile where resources are in demand.":
        "Пишна зелень майже сховала руїни міста, чиє ім'я відійшло в забуття. Вислухайте його німе свідчення: мир крихкий там, де потрібні ресурси.",
    "Every baby worm dreams of being a gladiator in the worm arena, where burly worms battle it out to eat sheep, grow, and squish their adversaries.":
        "Кожне дитинча хробака мріє стати гладіатором хробачої арени, де кремезні хробаки б'ються, щоб їсти овець, рости та роздавлювати суперників.",
    "Welcome to the dark side of the Amazon Forest... beware! \r\nStrange things may lie deep in the murky dark waters...":
        "Вітаємо на темному боці Амазонського лісу... стережіться!\r\nУ мутних темних водах можуть таїтися дивні речі...",
    "A massive land bridge leads to your opponent, while the surrounding shallows are inhabited by many other dangerous creatures.":
        "Величезний суходільний міст веде до вашого суперника, а навколишні мілини населені чималою кількістю інших небезпечних створінь.",
    "The cobbled road that cuts through this bandit-infested ridge is perilous and unsafe for travel. Restless thieves prowl in the night, paying their Ogre and Troll allies with the heads of foolhardy adventurers.":
        "Брукована дорога, що перетинає цей кряж, кишить розбійниками — подорож нею небезпечна. Несприкнені злодії бродять уночі, розплачуючись зі своїми союзниками-ограми та тролями головами недбалих мандрівників.",
    "This lake is the only water supply for miles. Mercenary Heroes have moved into the area to take advantage of the constant bloodshed. Wade into the glittering shallows at your own risk.":
        "Це озеро — єдине джерело води на багато миль. Наймані герої оселилися в окрузі, скориставшись безперервним кровопролиттям. Бродіть блискучими мілинами на власний ризик.",
    "Phat loot is ready for the taking within these concealed hills. But stay on the path or be lost forever.":
        "У цих прихованих пагорбах вас чекає розкішна здобич. Але тримайтеся стежки, інакше загинете назавжди.",
    "Though these islands are surrounded by deep and treacherous waters, they have seen little peace. Many of the creatures dwelling here are refugees from the war. They have nothing left to lose. Don't expect a warm welcome.":
        "Хоча ці острови оточені глибокими й підступними водами, спокою вони не знали. Багато створінь тут — біженці з війни. Їм нема чого втрачати. Не сподівайтеся на теплий прийом.",
    "Winter has reigned undisputed over this city ever since the Lich King's arrival. Now, at last, the ice has begun to melt.":
        "Відтоді як прибув Король-Ліч, зима безроздільно панує над цим містом. Тепер, нарешті, лід почав танути.",
    "The Cult of the Damned was known for massacring remote villages to supply their ghoulish experiments with innocents. With aerial support you can send the lieutenants of their latest raid back to Hell.":
        "Культ Проклятих славився вирізанням віддалених сіл, щоб постачати своїх страховиських піддослідних безневинними. З підтримкою з повітря ви можете відправити лейтенантів їхнього останнього рейду обратно до пекла.",
    "Challenge your enemy on the chosen ground of this country. From farmland to high ground, you will battle for supremacy.":
        "Перевірте свого ворога на обраному цією країною ґрунті. Від ферм до висот — ви битиметеся за верховенство.",
    "The Global Warming cannot be stopped and the last survivors turnout back to the upper Lands behind. Now, even the last dry lands are flooding and the last remainings are fighting for it.":
        "Глобальне потепління не зупинити, і останні вцілілі відступають до верхніх земель. Тепер вода заливає навіть останні сухі клапті, і решта борються за них.",
    "After a large snowstorm the snow began to melt and left the valley inundated. Therefore, murlocs have settled here, and they want to claim the treasures of the ogres, gnolls, and trolls. Now it's your turn to thaw your mind while exploring the area, and I hope your skills are not frozen.":
        "Після великого снігового шторму сніг почав танути й затопив долину. Тому тут оселилися мурлоки, які хочуть заволодіти скарбами огрів, гнолів і тролів. Тепер ваша черга — розморозьте свій розум, досліджуючи цей край, і сподіваюся, ваші навички не задубіли.",
    "Due to the harsh enviroments of Northrend, factions have begun seeking more suitable strongholds for their northren fleets. These isles will do nicely for any faction that can secure them.":
        "Через суворі умови Нортренда фракції почали шукати придатніші твердині для своїх північних флотів. Ці острови підійдуть будь-якій фракції, яка зможе їх утримати.",
    "Once a bustling trade route, this path has become a rain-sodden swampland infested with brigands and kobold mongrels. Gain a foothold and capture the strategic center.":
        "Колись жвавий торговий шлях перетворився на промокле болото, кишаче розбійниками та кобольдськими виродками. Здобудьте плацдарм і захопіть стратегічний центр.",
    "Since ages past, there is a story told in the taverns about a secret, flooded valley where shallow water can become the grave of the incautious.":
        "З давніх-давен у тавернах розповідають історію про таємну затоплену долину, де дрібна вода може стати могилою для необережних.",
    "There once existed a shrine to the ancient gods of yore, but all that remains is a ruin of rubble, sand, and ore. Though legends persist of creatures from the sea, that have surfaced to guard the treasures of an era long before.":
        "Колись тут стояло святилище давніх богів, але від нього лишилися руїни з щебеню, піску й руди. Хоча легенди й досі говорять про створіння з моря, що спливли на поверхню, щоб вартувати скарби доби, що настала задовго до наших часів.",
    "Scientists who were excavating a sunken temple discovered some long lost ancestral artifacts. When the greedy goblins realized what these ancient ruins were hiding, they began to flood the researcher's village and claim the sacred grounds.":
        "Вчені, які досліджували затонулий храм, виявили давно втрачені артефакти предків. Коли жадібні гобліни збагнули, що ховають ці давні руїни, вони почали затоплювати село дослідників і захоплювати священні землі.",
    '"Noble countrymen, evil is upon us. Darkness has befallen our shores. Rise and slay thy enemies… strike, strike so others shall live. The meek shall not fade into the night… live my brethren, live.” –King Terenas':
        "«Шляхетні співвітчизники, зло уже тут. Темрява поглинула наші береги. Встаньте й вбийте ворогів своїх... бийте, бийте, щоб жили інші. Смиренні не згинуть у ночі... живі, браття мої, живі». — Король Теренас",
    "Separated from your enemy by two narrow bridges, you might find a Goblin Zeppelin useful in fending off attacks or dropping off a raiding party.":
        "Розділені з ворогом двома вузькими мостами, ви, можливо, знайдете гоблінський дирижабль корисним для відбиття атак або висадки рейдового загону.",
    "Restless servants of the Undead linger to the east and west, but the rain has washed most of these glades clean of the Scourge's taint.":
        "Несприкнені слуги нежиті крадуться сходом і заходом, але дощ відмив більшість цих гаїв від сквери Плачу.",
    "Navigate through the meandering streams on Nomad Isles to defeat your opponents.":
        "Подолайте звивисті потоки Кочових Островів, щоб перемогти своїх суперників.",
    "Vie for supremacy, north versus south, amidst the snow-capped peaks of Lordaeron. Thirsty? Then hurry. Each team has its own Fountain, but the Taverns are first come, first served.":
        "Змагайтеся за верховенство: північ проти півдня серед засніжених вершин Лордерону. Спраглий? Тоді поспішайте. У кожної команди свій Фонтан, але таверни дістаються тим, хто перший.",
    "Four islands have been linked to a central landmass, thanks to clever engineering. Cross the sturdy wooden bridges to invade enemy towns, but be sure to protect your own bridges in the meantime.":
        "Завдяки хитромудрій інженерії чотири острови з'єдналися з центральним масивом суходолу. Переходьте міцні дерев'яні мости, щоб вторгнутися у ворожі міста, але не забудьте тим часом захистити власні мости.",
    "In the center of this arctic area is a Tavern that hires out mercenary Heroes. With their assistance, you might gain an edge over your enemies.":
        "У центрі цього арктичного краю стоїть Таверна, що наймає героїв-найманців. З їхньою допомогою ви можете здобути перевагу над ворогами.",
    "The unforgiving winter is upon us… a time when resources are scarce and flanks exposed. Call forth the warriors, for there could not be a better time to attack than now.":
        "Невблаганна зима настала... час, коли ресурси мізерні, а фланги відкриті. Закличте воїнів, бо найкращого моменту для атаки, ніж зараз, не буває.",
    "The centaur tenaciously defend these meadows, which are believed to be holy. Mystical waygates provide a quick way to travel across the land.":
        "Кентаври вперто захищають ці луки, які вважаються священними. Містичні Брами Шляхів дають змогу швидко подорожувати цим краєм.",
    "In the arctic cold, hunger and bitterness have driven many individuals to desperate measures. Every loyalty has a price. Keep a steady supply of gold at hand.":
        "У арктичному холоді голод і гіркота штовхають багатьох на відчайдушні кроки. Кожна вірність має свою ціну. Тримайте під рукою стабільний запас золота.",
    'For years the mages of Moonbrook have debated, "If a brave warrior falls in a forest with no one to hear it, then does it make a sound?"':
        "Роками маги Мунбрука сперечалися: «Якщо хоробрий воїн упаде в лісі, і ніхто цього не почує, чи пролунає звук?»",
    "The Deathrose is a rare flower that grows only in the deepest, darkest swamps of Ashenvale. In the hands of a master alchemist, the petals of the flower can be used to create some of the deadliest poisons known to exist in all Azeroth.":
        "Троянда Смерті — рідкісна квітка, що росте лише в найглибших і найтемніших болотах Ясеневого лісу. У руках майстра-алхіміка її пелюстки стають складниками найсмертоносніших отрут, відомих у всьому Азероті.",
    "Each player starts on a high bluff, and can only reach other players by using a Goblin Zeppelin. As a result, Goblins in this region are more annoyingly prosperous than ever.":
        "Кожен гравець починає на високому обриві й може дістатися інших лише на гоблінському дирижаблі. Тож гобліни в цих краях процвітають дратівливо як ніколи.",
    "There is no escape from the searing heat. Many dark things thrive in this sulfurous environment, but it's unlikely you will. Seek out the Fountains of Health, or hire your own monstrous allies.":
        "Від пекельного спеку немає порятунку. У цьому сірчаному середовищі процвітає чимало темних істот, але ви навряд чи з них. Знайдіть Фонтани Здоров'я або найміть власних огидних союзників.",
    "With the help of Gazlowe's engineers, an unexplored city was recently excavated near Durotan. Quickly secure the gold mines in the center before your enemies do.":
        "За допомогою інженерів Газлоу недосліджене місто нещодавно розкопали біля Дуротана. Швидко займіть золоті копальні в центрі, доки цього не зробили вороги.",
    "Follow the streams to your enemy's town, but beware. There are Ogres in the gully.":
        "Рухайтеся струмками до міста ворога, але стережіться: у яру сидять огри.",
    "A land of peace and plenty... of manip.":
        "Край миру та достатку... маніпуляцій.",
    "The four-leaf clover is seen as an omen of good luck. Venture into this clover's heart too soon, though, and all the luck in the world will avail you nothing.":
        "Чотирилиста конюшина вважається знаком удачі. Але якщо забратися в серце цієї конюшини надто рано, уся удача світу вам не допоможе.",
    "Beauty has given way to the beasts – Furbolgs lurk around every bend. Survival is key to victory.":
        "Краса поступилася звірам — фурболги підстерігають за кожним поворотом. Виживання — запорука перемоги.",
    "War and hunger have brought interlopers to Elwynn Forest, endangering the town of Goldshire. Sweep the woods free of this threat so that masons can begin laying the foundation of Stormwind.":
        "Війна й голод привели чужинців до Ясеневого лісу, поставивши під загрозу містечко Златозілля. Очистіть ліс від цієї загрози, щоб муляри могли закласти фундамент Штормграду.",
    "Amidst these snowy pines, an enterprising band of Goblins is capitalizing on this region's conflict. Swallow your scruples, and make haste. To them, your opponents' gold is just as welcome as your own.":
        "Серед цих засніжених сосен заповзятий загін гоблінів наживається на конфлікті в регіоні. Приглушіть сумніви й поспішайте: для них золото ваших суперників так само приємне, як і ваше власне.",
    "Once a thriving mining region, Hearthglen Hills is now overrun with vile creatures who scrounge for what little gold remains.":
        "Колись квітнучий гірничий край, Пагорби Герстґлену тепер кишать огидними створіннями, які викопують те мале золото, що лишилося.",
    "Shattered beyond repair by powerful magics, the Orc homeland is a landscape of broken dreams and despair. Only those with an iron will can overcome the armies of Hellfire.":
        "Розбита могутньою магією так, що вже не відбудувати, батьківщина орків — це краєвид розбитих мрій і відчаю. Лише ті, хто має залізну волю, здолають армії Пекельного Полум'я.",
    "Thanks to their brawny allies, the Ice Trolls have ruled this arctic land, undisputed, far too long. Secure in their power, they have grown careless and soft. They are ripe for conquest.":
        "Завдяки своїм кремезним союзникам крижані тролі безроздільно панують над цим арктичним краєм уже надто довго. Впевнені у своїй силі, вони задурмилися й розм'якли. Настав час завоювання.",
    "In the frozen tundra, dark powers and magical weapons were forged upon the cold, perilous lands of Ice Forge.":
        "На крижаних тундрах, у холодних і небезпечних землях Крижаної Кузні кувалися темні сили й магічна зброя.",
    "A great civilization once inhabited this sunny archipelago. Now its shipyards are overrun by Mur'gul, and other even more precious resources are guarded by a massive Dragon Turtle and her offspring.":
        "Колись на цьому сонячному архіпелазі жила велика цивілізація. Тепер його верфі захопили мургули, а інші, ще цінніші ресурси вартує величезний Дракон-Черепаха зі своїм потомством.",
    "Scouts have spotted strange pillars of stone in Ashenvale. These Monoliths seem to imbue the woodland creatures with a new and deadly purpose. Destroy the Monoliths to free the forest from their control.":
        "Розвідники помітили в Ясеневому лісі дивні кам'яні стовпи. Ці Моноліти, здається, надають лісовим створінням нову й смертоносну мету. Зруйнуйте Моноліти, щоб звільнити ліс від їхньої влади.",
    "This verdant paradise is as plentiful in resources as it is in foes. Enter the shallows with a solid fighting force. Beware the spellcasters who hold the temple ruins.":
        "Цей пишний рай такий же багатий на ресурси, як і на ворогів. Виходьте на мілини з міцним бойовим загоном. Стережіться заклиначів, що тримають руїни храму.",
    "An ancient horror lurks in these twisting paths turning away all but the most stalwart of champions. These would-be heroes enter confidently, seeking battle and adventure to immortalize their legacy... but none have returned.":
        "У цих звивистих стежках ховається давній жах, що відвертає всіх, окрім найстійкіших championів. Такі собі майбутні герої входять впевнено, шукаючи битв і пригод, щоб увічнити свою славу... але жоден не повернувся.",
    "Over the millennium, many hard-won battles have assured a place where fallen generals and countless soldiers of history watch over this land forever.":
        "Протягом тисячоліть багато здобутих у тяжких боях перемог забезпечили цьому місцю долю: полеглі полководці та незчисленні воїни історії назавжди вартують цю землю.",
    "Sharp ridges of rock pierce the sky, offset by pools born from underground hot springs. The main path winds around such obstacles, but keep an eye out to avoid getting run down by an enemy.":
        "Гострі скельні хребти пронизують небо, чергуючись із басейнами, народженими підземними гарячими джерелами. Головна дорога звивається навколо таких перешкод, але тримайте очі відкриті, щоб не потрапити під ніс ворога.",
    "Despite the city's age, its beauty has not yet been entirely reduced to rubble. Dotted with trees and paved in decorative tile, it can still be reclaimed from the wilderness.":
        "Незважаючи на вік міста, його краса не звернулася повністю на руїни. Усіяне деревами й вимощене декоративною плиткою, воно все ще можна відвоювати в дикої природи.",
    "The blizzard that once made the high crags of Stone Cold Mountain inaccessible has finally subsided. Rumor has it that the first expeditionary force sent to explore the area returned battered and broken. Time, it seems, has only made the mountain deadlier.":
        "Хуртовина, яка колись робила високі скелі Гори Кам'яного Холоду недосяжними, нарешті вщухла. Ходять чутки, що перша експедиція, послана дослідити цей край, повернулася побита й знесилена. Здається, час лише зробив гору смертельнішою.",
    "An ancient power echoes across the cerulean land. Two forces, bound in an endless struggle, united they stand. Forever shall they be in strife, an ethernal misery. Though never alone, as one cannot stand without the other, for this is Synergy.":
        "Давня сила лунає над бірюзовим краєм. Дві сили, пов'язані у вічній боротьбі, разом вони стоять. Назавжди їм суджена ворожнеча, вічна мука. Але ніколи не поодинці, бо один не може стояти без іншого, — бо це Синергія.",
    "This once-quiet peninsula is now inhabited by packs of Centaur and Razormanes. To the east and west lie enchanted Fountains; to the north and south, Goblin technology that may prove handy.":
        "Цей колись спокійний півострів тепер населений зграями кентаврів і бритвенців. На сході й заході — зачаровані Фонтани; на півночі й півдні — гоблінські технології, які можуть знадобитися.",
    "These lush glades contain many treasures, but also dangers. Be careful not to be caught off-guard while admiring the view because your opponent might ambush your party.":
        "У цих пишних гаях багато скарбів, але й небезпек. Не дайте себе застати зненацька, милуючись краєвидами, — суперник може влаштувати засідку вашому загону.",
    "Once an island for all those who were exiled, this has now become an island of riches for those who seek its hidden treasures.":
        "Колись острів для всіх вигнанців, тепер він став островом багатства для тих, хто шукає його приховані скарби.",
    "The path twists, and the future is uncertain. Race for the center and the treasures it might hold, or visit a Goblin Laboratory and explore one of the small islands.":
        "Шлях звивається, і майбутнє невизначене. Перегоніть до центру й скарбів, які він може приховувати, або завітайте до гоблінської лабораторії та дослідіть один із малих островів.",
    "Renegade spellcasters restrict all trade here, secure in the power of their magic. Outside the city walls, pitiless enemies greet the unwary.":
        "Відступники-заклиначі обмежують тут усю торгівлю, спокійні в силі своєї магії. За міськими мурами безжальні вороги зустрічають необережних.",
    "Fed by crystalline waterfalls, the jungle has devoured all but a few bricks of what was once a thriving metropolis. Take advantage of what the current denizens have to offer.":
        "Підживлювані кристалічними водоспадами, джунглі поглинули все, крім кількох цеглин, від колись квітнучого мегаполісу. Скористайтеся тим, що пропонують нинішні мешканці.",
    "A group of Owlbears has established a monopoly on providing mercenaries in this region. Meanwhile, Goblin Merchants remain on the sidelines of the fray and rake in a tidy profit.":
        "Зграя совеведмедів монополізувала надання найманців у цьому регіоні. Тим часом гобліни-торгаші тримаються осторонь сутички й згрібають чималий прибуток.",
    "Teams must defend a single ramp and a Way Gate that provides easy access for invaders. The key lies not in defense, but in controlling the Wastes.":
        "Команди мають обороняти єдиний підйом і Браму Шляхів, що дає загарбникам легкий доступ. Ключ не в обороні, а в контролі над Пустками.",
    "Stone bridges provide passage over this city's canals. Thanks to the local Goblin Laboratories, though, a quicker method of transport is available.":
        "Кам'яні мости перекинуті через канали цього міста. Але завдяки місцевим гоблінським лабораторіям є і швидший спосіб пересування.",
    "The most hardened criminals in the universe are held here, in a jail devised by those that would rather never see such vile creatures set free.":
        "Тут тримають найзатятіших злочинців всесвіту — у в'язниці, створеній тими, хто хотів би ніколи не бачити цих огидних істот на волі.",
    "There is no water as far as the eye can see. During the day, beneath the unforgiving sun, it's a struggle to survive. One Tavern is open for business; its mercenaries may tip the scales in your favor.":
        "Води не видно, наскільки хапає око. Удень, під невблаганним сонцем, вижити — боротьба. Одна Таверна відкрита: її найманці можуть схилити терези на вашу користь.",
    "Warring Marines have taken over Icecrown Glacier. Command your bomber force to destroy your opponent's town while scrambling to defend your own.":
        "Воюючі морпіхи захопили льодовик Крижаної Корони. Командуйте своїми бомбардувальниками, щоб зруйнувати місто суперника, поспішаючи захистити власне.",
    "Devastated by clashing armies and their blistering waves of magic, this wasteland's only remaining value is as a strategic chokehold. In the right hands, it will turn the tides of war.":
        "Спустошений зіткненнями армій та їхніх пекельних магічних хвиль, цей край цінний лише як стратегічний вузол. У правильних руках він переломить хід війни.",
    "The most loathsome and malevolent of creatures have settled here. Sleepless malice keeps them locked in eternal conflict, so that even the river stinks of death.":
        "Тут оселилися найогидніші й найпідступніші створіння. Неспящий зліст тримає їх у вічному конфлікті, так що навіть річка смердить смертю.",
    "Those who have braved the chill wind speak of a graveyard called Dragonblight. Treasure is rumored to lie beneath draconian bones, but vigilant dragons watch this sacred ground for foolhardy graverobbers.":
        "Ті, хто витримав крижаний вітер, розповідають про цвинтар під назвою Драконяча Пустош. Ходять чутки, що під драконячими кістками заховані скарби, але пильні дракони вартують цю священну землю від недбалих грабіжників могил.",
    "These barren wastes hold nothing for the living, harboring only the bones of those who have fallen to the sun bleached land. The dusty earth thus serves as a savage battleground where armies can unleash their full might unhindered.":
        "Ці голі пустки не дають живим нічого, ховаючи лише кістки тих, хто впав на вибілену сонцем землю. Пилова земля слугує жорстоким полем бою, де армії можуть сповна вивільнити свою міць без перешкод.",
    "Fleets sail from distant lands to loot the treasures of this ancient island.  Some even come to brave the mystic defenders of the ancient temple… others know better.":
        "Флоти припливають з далеких земель, щоб пограбувати скарби цього давнього острова. Дехто навіть наважується кинути виклик містичним вартовим давнього храму... інші знають краще.",
    "When Enakro faced Tasarus, the ground was torn asunder and the valley was divided in two.":
        "Коли Енакро зіткнувся з Тасарусом, земля розтріскалася, і долина розділилася надвоє.",
    "Hidden deep within the wintry crags of Everfrost is a realm of dark Nerubian horrors, protecting their frozen crypt from those that seek gold and wealth. Only when working together can these chilling nightmares be defeated and vanquished under ice forever.":
        "Глибоко в зимових скелях Вічної Мерзлоти ховається володіння темних неруб'янських жахів, що захищають свій замерзлий склеп від тих, хто шукає золота й багатства. Лише об'єднавшись можна перемогти ці крижані жахіття й повергнути їх під лід назавжди.",
    "Forged from the remnants of Draenor, this long-forgotten island was once a haven for outcasts. Now all that remains are relics of ancient battles and lost souls.":
        "Створена з решток Дренору, ця давно забута людом острів колись була притулком вигнанців. Тепер від неї лишилися лише реліквії давніх битв і загублені душі.",
    "Highperch bestows beauty and magical powers to those brave enough to withstand savage attacks from the inhabitants who protect its secret healing waters.":
        "Високий Виступ дарує красу й магічні сили тим, хто досить хоробрий, щоб витримати дикі атаки мешканців, які охороняють його таємні цілющі води.",
    "Deep in the woods, you track down the enemy encampment and prepare to launch a final, decisive strike. Assemble your forces quickly: the peril is great, and time grows short.":
        "Глибоко в лісі ви вистежуєте ворожий табір і готуєте останній, вирішальний удар. Зберіть сили швидко: небезпека велика, а часу дедалі менше.",
    "Take heed while you explore these eerie lands. You may find that the dead have a distinctly odd sense of humor. Is that the gleam of polished steel, or the glitter of gold? Trick... or treat?":
        "Стережіться, досліджуючи ці моторошні землі. Можливо, ви виявите, що мертві мають дивакувате почуття гумору. Чи то блиск відшліфованої сталі, чи то іскра золота? Витівка... або гостинець?",
    "Slowly but inexorably, this peninsula is sinking into the sea. Team up and wade into the shallows, but keep an eye out. Dangerous beasts lurk in these salty waters.":
        "Повільно, але невблаганно цей півострів іде під воду. Об'єднуйтеся та бродіть мілинами, але тримайте очі відкритими: у солоних водах підстерігають небезпечні звірі.",
    "Ogres and Trolls hold most of the local riches, but Golems maintain a sleepless vigil over the island's center.":
        "Огри й тролі володіють більшістю місцевих багатств, але големи безсонно вартують центру острова.",
    "From the old days, twisted death 4 everyone! Neon City gave birth to Moon and Sun - the most diabolic critters to grace Azeroth.\r\n\r\nSoundtrack to this city: The Claws are Coming!":
        "Зі старих часів — викривлена смерть для всіх! Неонове Місто породило Місяць і Сонце — найпідступніших тварюок Азероту.\r\n\r\nСаундтрек цього міста: The Claws are Coming!",
    "Azeroth's bread basket has now become an endless sea of the dead as war grips this once calm farmstead.":
        "Житниця Азероту перетворилася на безкрайнє море мертвих, коли війна охопила колись спокійну ферму.",
    "This war has raged for generations. Don't be deceived by the river's clarity. Its icy waters have often run red with blood, and soon the River of Souls will feast on the fallen again.":
        "Ця війна триває поколіннями. Не дурійте ясністю річки. Її крижані води часто червоніли від крові, і скоро Ріка Душ знову бенкетуватиме на полеглих.",
    "Thump... Thump... War approaches. Booming drums call the troops to death and glory. The lines are drawn, and alliances are set. Nothing will hold back the bloodshed. War is here.  Thump... Thump!":
        "Туп... Туп... Війна наближається. Гуркіт барабанів кличе війська до смерті й слави. Лінії проведено, союзи укладено. Нічого не стримає кровопролиття. Війна тут. Туп... Туп!",
    "Stratholme was once a bastion of Alliance power but now it stands as a burning testament to the evil of the Scourge. Only the bravest of heroes would dare enter this ruined city, for the undead armies of Kel’Thuzad still hold sway over the haunted capital.":
        "Стратхольм колись був бастіоном сили Альянсу, але тепер стоїть палаючим свідченням зла Плачу. Лише найхоробріші герої наважаться увійти в це зруйноване місто, адже армії нежиті Кел'Тузада досі тримають у владі прокляту столицю.",
    "Expand quickly and fight your way through the snow to purchase magical items and hire allies. You would do well to establish a base upon the heights, but their isolation alone will not save you.":
        "Розширюйтеся швидко й пробивайтеся крізь сніг, щоб купити магічні предмети й найняти союзників. Непогано було б збудувати базу на висотах, але сама їхня ізоляція вас не врятує.",
    "Conveniently close by, mercenary Heroes are available for hire. Among these rich resources and forested hills, you could team up with allies or strike out on your own.":
        "Поруч, як на вибір, доступні для найму герої-найманці. Серед цих багатих ресурсів і заліснених пагорбів ви можете об'єднатися з союзниками або діяти самостійно.",
    "Crumbling columns and faded statuary dot this verdant island, now thickly overgrown and populated by an unusually large number of spellcasters. Rouse their ire at your own risk.":
        "Розсипані колони й побляклі статуї всіяні цим пишним островом, тепер густо зарослим і населеним незвичайно великою кількістю заклиначів. Розгнівати їх — на ваш страх і ризик.",
    "Sunrock Cove is a famous getaway for those with a lot of gold to explore its rich area. Remember to tip your Goblin Zeppelin after he rides you to a most pleasurable victory!":
        "Бухта Сонячної Скелі — знамените місце відпочинку для тих, у кого багато золота, щоб дослідити її багаті землі. І не забудьте дати на чай своєму гоблінському дирижаблю після того, як він прокатить вас до найприємнішої перемоги!",
    "A landmark for travelers, this star-shaped lake is home to the plains' toughest creatures. Not by coincidence, it's also ringed by the richest gold mines. Take them if you dare. Defend them if you can.":
        "Орієнтир для мандрівників, це зірчасте озеро є домом для найлютіших створінь рівнин. І не випадково воно оточене найбагатшими золотими копальнями. Заберіть їх, якщо наважитеся. Відстоїте, якщо зможете.",
    "Coastal fog has enshrouded this archipelago. Be wary as you pass from one island to the next: there is no telling what leviathans lie sleeping in this cold sea.":
        "Прибережний туман огорнув цей архіпелаг. Стережіться, переходячи з острова на острів: невідомо, які левіафани сплять у цьому холодному морі.",
    "Here in the shattered kingdom of Azjol-Nerub, pillars of ice pierce the land like the teeth of an enormous beast. Perhaps recruiting an ally from the native inhabitants would be wise.":
        "Тут, у розбитому королівстві Азжол-Неруб, крижані стовпи пронизують землю, як зуби величезного звіра. Мабуть, розумно буде завербувати союзника з числа місцевих мешканців.",
    "Golems guard a sacred Fountain while Bandits hide in the shadows. Unless you are fond of pain, do not venture into the central enclosure without a powerful allied army.":
        "Големи вартують священного Фонтану, а розбійники ховаються в тіні. Якщо ви не фанат болю, не наважуйтеся в центральне огородження без потужної союзної армії.",
    "An invading force of Dark Trolls swept this island like a plague not too long ago. Most of the Furbolgs who once thrived here were slaughtered; the few survivors have scattered into hiding.":
        "Не так давно орда темних тролів пройшла цим островом, як мор. Більшість фурболгів, що колись тут процвітали, вирізано; ті нечисленні, хто вижив, розсіялися та сховалися.",
    "Nestled in the Arathi Foothills lies the pristine resort enclave where the wizards of Dalaran retreat from the front lines to recuperate while relaxing in steamy hot mana pools.":
        "У підніжжі Аратіських пагорбів ховається бездоганний курортний анклав, куди чарівники Даларану відступають з ліній фронту, щоб відновитися, розслабляючись у гарячих манна-басейнах.",
    "Legends speak of a hidden race track north of the border where representatives from the far reaches of the land gather to test their skills and racing prowess. This event is known to break even the mightiest of combatants with its no-rules-barred arena.":
        "Легенди говорять про приховану трасу за кордоном, куди з'їжджаються представники найвіддаленіших куточків країни, щоб випробувати свою майстерність і гоночну звитягу. Ця подія відома тим, що ламає навіть наймогутніших бійців ареною без жодних правил.",
    "Cruel magic has demented this forest's denizens beyond any hope of healing. Now they attack the World Tree, hoping to corrupt it in the misguided belief that it will end their agony. Protect the Tree.":
        "Жорстока магія звела з розуму мешканців цього лісу поза жодною надією на зцілення. Тепер вони атакують Світове Дерево, сподіваючись осквернити його в оманливій вірі, що це покладе край їхнім мукам. Захистіть Дерево.",
    "This land is truly cursed. Rivers of poison, filled with demonic bile, eat away at the earth. Ancient wyrms, terrible and great, slumber quietly within the mire. Perhaps you know of a dragon slayer, jobless, up for hire.":
        "Ця земля справді проклята. Ріки отрути, повні демонічної жовчі, виїдають землю. У трясовині тихо сплять давні, страшні й величезні віруни. Може, ви чули про вбивцю драконів — безробітного, готового на найм?",
    "Cherryville holds the truth of nature... from the vines, life grows and from the sheath, death follows. Those that wield both crush all those that oppose.":
        "Вишневиця тримає правду природи... з лози росте життя, а з піхви йде смерть. Ті, хто володіє обома, тіснять усіх, хто проти.",
    "Decorated with the bones of long-dead adventurers, this desolate expanse of rock seems to have little worth fighting over. Yet the locals often lock horns over every barren inch. Join the fray if you can.":
        "Прикрашені кістками давно загиблих мандрівників, ці безплідні скелі, здається, не варті боротьби. Але місцеві часто гризуться за кожен голий клапоть. Приєднуйтеся до сварки, якщо зможете.",
    "After a bloody deadlock that lasted three long years, the Centaur became the undisputed rulers of these wild plains. Claim as many gold mines as possible, or you will fall to the hate of your enemy.":
        "Після кривавого пату, що тривав три довгі роки, кентаври стали беззаперечними володарями цих диких рівнин. Захопіть якомога більше золотих копалень, інакше впадете від ненависті вашого ворога.",
    "Pockets of deep water have complicated the process of getting around in this wooded region. It may prove simpler to seek out air transportation.":
        "Кишені глибокої води ускладнили пересування в цьому лісовому краї. Можливо, простіше шукати повітряного транспорту.",
    "Deep in the Ashenvale forest is a grove under the intermittent protection of a deadly Green Dragon. Word has it this region is only safe for travel in winter... or was that summer?":
        "Глибоко в Ясеневому лісі є гай під нечастою охороною смертельно небезпечного зеленого дракона. Кажуть, цей край безпечний для подорожей узимку... або це влітку?",
    "Separated only by a shallow stretch of water, two teams prepare to battle it out. The forest is dense enough that you may need to chop through the trees in order to better aid your allies.":
        "Розділені лише смугою мілкої води, дві команди готуються звести рахунки. Ліс настільки густий, що, можливо, доведеться прорубувати дерева, щоб краще допомагати союзникам.",
    "Revisit an old favorite: team up with an ally to build shared bases. On the central hill, magical Fountains await, but their massive guardians are highly resistant to magic.":
        "Повернення до старої улюбленої ідеї: об'єднайтеся з союзником, щоб будувати спільні бази. На центральному пагорбі чекають магічні Фонтани, але їхні величезні вартові вкрай стійкі до магії.",
    "In these eternally contested lands, war comes and goes leaving behind death and glory. Strike strategically and fight valiantly till your foes fall and you can hear the snowflakes land on the dead. Victory, at last.":
        "На цих вічнопорушених землях війна приходить і минає, лишаючи по собі смерть і славу. Завдавайте ударів стратегічно й бийтеся доблесно, поки вороги не впадуть і ви не почуєте, як сніжинки падають на мертвих. Нарешті — перемога.",
    "Hunt for eggs on Bunny Island. The Easter Bunny will share his eggs if you can catch up with him. Be careful, though: the island hosts a gang of evil bunnies who will try to stop you.":
        "Полюйте на яйця на Острові Кролика. Великодній Кролик поділиться своїми яйцями, якщо ви його наздоженете. Але обережно: на острові діє банда злих кролів, які спробують вас зупинити.",
    "Squads of hostile creatures have these woods in a stranglehold and the central gold mines are unguarded. Do you have the courage to stake your claim?":
        "Ватаги ворожих створінь тримають ці ліси в смертельних обіймах, а центральні золоті копальні без охорони. Чи вистачить вам відваги заявити на них права?",
    "This land is shot with veins of gold, gleaming with the promise of wealth and power. Don't be lured into complacency. Expand early and often, or you cannot hope to achieve greatness.":
        "Ця земля просякнута золотими жилами, що сяють обіцянкою багатства й влади. Не дайте себе приспати. Розширюйтеся рано й часто, інакше не мрійте про велич.",
    "In one of the most tumultuous and dangerous parts of the ocean lies an isle run by goblins. Their whole lot in life is to sell zeppelins to wayward seafarers whose ships were destroyed by perilous hurricanes common to these waters.":
        "В одному з найбурхливіших і найнебезпечніших куточків океану лежить острів, яким керують гобліни. Їхнє все життєве покликання — продавати дирижаблі заблудлим мореплавцям, чиї кораблі знищили небезпечні урагани, звичні для цих вод.",
    "Though densely populated, this land also offers rich prospects. With enough gold, you can hire additional troops. Explore the northern and southern isles, where even more powerful allies can be found.":
        "Хоча цей край густо заселений, він також пропонує багаті перспективи. З достатнім золотом ви можете найняти додаткові війська. Дослідіть північні й південні острови, де знайдуться ще могутніші союзники.",
    "This city was laid out by meticulous architects. Regrettably its wide streets and simple elegance attracted the attention of a passing warlord, whose army invaded the city shortly thereafter.":
        "Це місто розпланували педантичні архітектори. На жаль, його широкі вулиці й проста елегантність привернули увагу одного воєначальника, чиє військо незабаром вторглося в місто.",
    "Mur'guls have long called this wetland oasis their home, and even more dangerous creatures lurk in the marsh. Encroach on their territory with extreme caution.":
        "Мургули давно називають цей заболочений оазис домом, а в трясовині підстерігають ще небезпечніші створіння. Зазіхайте на їхню територію з надзвичайною обережністю.",
    "Utilize the strengths of different spawn locations and work with your team to take map control and overcome your adversaries in this ancient battlefield, located within the Nerubian Kingdom.\r\n\r\nWinner of the Hive Workshop Melee Mapping Contest #3":
        "Використовуйте переваги різних точок появи і працюйте з командою, щоб узяти контроль над картою та подолати суперників на цьому давньому полі бою в Неруб'янському королівстві.\r\n\r\nПереможець конкурсу Hive Workshop Melee Mapping Contest #3",
    "Spellcasters and thieves control much of these ruins. Challenging them at night could result in an unpleasant surprise.":
        "Заклиначі й злодії контролюють більшу частину цих руїн. Виклик їх уночі може обернутися неприємним сюрпризом.",
    "The Last Guardian, Medivh, once lived in this desolate place. Face the lingering magics, and silence the ghosts that haunt his former home. Beware the enclosed city: it is certain death for the unprepared.":
        "У цьому безплідному місці колись жив Останній Вартовий, Медів. Зіткніться з рештками магії та вгамуйте привидів, що блукають його колишнім домом. Стережіться замкненого міста: для неготових це верна смерть.",
    "Team up and risk the city's brutal inhabitants as soon as you can. The treasures they guard could easily turn the tide of battle.":
        "Об'єднуйтеся й ризикуйте зіткнутися з брутальними мешканцями міста щойно можете. Скарби, які вони вартують, можуть легко переломити хід битви.",
    "There's lush greenery in every direction, but nary a spare coin to be found. Still, with a wee bit o' luck, you and your neighbor can earn a bounty by slaying any beasties nearby.":
        "Пишна зелень скрізь навколо, але й зайвої монети не знайдеш. Утім, із часткою удачі ви й ваш сусід можете заробити винагороду, вбиваючи місцевих звірят.",
    "Even this far south, Northrend has no mercy. Bitter winds slice through the thickest clothes, and cunning arctic beasts race down the slopes to prey upon unsuspecting settlers.":
        "Навіть такий далекий південь Нортренда не знає милосердя. Гіркі вітри прорізають найгустіший одяг, а хитрі арктичні звірі мчать схилами, щоб полювати на необережних поселенців.",
    "The ocean has carved deep rivers in the land and formed what looks like a giant spider. Bridges offer one way to get around, but don't kid yourself: the best transport here is of Goblin manufacture.":
        "Океан прорізав у землі глибокі ріки й утворив те, що схоже на гігантського павука. Мости — один спосіб пересування, але не обманюйте себе: найкращий транспорт тут — гоблінського виробництва.",
    "Positioned so as to extract the maximum amount of profit, Goblin Merchants and mercenaries sell their services to the quickest bidder. Expand quickly, or you'll be overrun.":
        "Розташовані так, щоб видобути максимальний прибуток, гобліни-торгаші й найманці продають свої послуги тому, хто швидше заплатить. Розширюйтеся швидко, інакше вас затопчуть.",
    "This sunken island holds many perilous opportunities for adventurous parties to besiege and conquer their opponents.":
        "Цей затонулий острів таїть багато небезпечних можливостей для відчайдушних загонів, які прагнуть обложити й підкорити своїх суперників.",
    "Ringed by Fountains, this forested island is not a place to explore alone. Visit the shops soon, but don't bother to take the central gold mines until you can keep them.":
        "Оточений Фонтанами, цей заліснений острів — не місце для поодинокої прогулянки. Невдовзі завітайте до крамниць, але не клопочіться про центральні золоті копальні, доки не зможете їх утримати.",
}
