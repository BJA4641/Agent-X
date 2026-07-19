"""niches.py — the top 20 paying niches for short-form content in 2026,
with 5 pre-designed brand accounts per niche (each with its own angle/tone/visual identity).
Used by the seed-demo API and by the Architect for fallback dossiers when LLM is off.

Ranking criteria for "top paying": affiliate RPM, YPP CPM, brand deal rates,
digital-product margin, proven faceless winners on TikTok/IG/Shorts.
"""

NICHES = [
    # --- MONEY / FINANCE ---
    {"slug":"ai_tools","emoji":"🤖","name":"AI tools & automation",
     "accounts":[
       {"name":"AI Tool Daily","handle":"aitool.daily","emoji":"🤖","platforms":["instagram","tiktok","youtube_shorts"],"angle":"one AI tool a day, hyper-specific"},
       {"name":"Prompt Hacks","handle":"prompt.hacks","emoji":"✨","platforms":["instagram","tiktok"],"angle":"copy-paste prompts that save hours"},
       {"name":"Agent Lab","handle":"agentlab","emoji":"🧠","platforms":["tiktok","youtube_shorts","x"],"angle":"autonomous AI agents / agentic workflows"},
       {"name":"Code Faster","handle":"codefaster","emoji":"💻","platforms":["youtube_shorts","x"],"angle":"AI for devs, 10x workflows"},
       {"name":"AI Money Moves","handle":"ai.money","emoji":"💰","platforms":["instagram","tiktok"],"angle":"AI side hustles that actually pay"},
     ]},
    {"slug":"finance","emoji":"💰","name":"Personal finance & side hustles",
     "accounts":[
       {"name":"Side Hustle Lab","handle":"sidehustle.lab","emoji":"💸","platforms":["instagram","tiktok","youtube_shorts"],"angle":"one actionable side hustle per post"},
       {"name":"Invest Simple","handle":"invest.simple","emoji":"📈","platforms":["youtube_shorts","instagram"],"angle":"beginner investing without the jargon"},
       {"name":"Budget Bro","handle":"budget.bro","emoji":"💵","platforms":["tiktok","instagram"],"angle":"save money hacks, frugal living"},
       {"name":"FIRE Diaries","handle":"fire.diaries","emoji":"🔥","platforms":["youtube_shorts","x"],"angle":"early retirement, financial independence"},
       {"name":"Credit Fix","handle":"credit.fix","emoji":"💳","platforms":["instagram","tiktok"],"angle":"credit score hacks, travel hacking"},
     ]},
    {"slug":"make_money_online","emoji":"🤑","name":"Make money online",
     "accounts":[
       {"name":"Print On Demand Pro","handle":"pod.pro","emoji":"👕","platforms":["tiktok","instagram","youtube_shorts"],"angle":"print-on-demand tutorials and results"},
       {"name":"YouTube Growth Lab","handle":"yt.growth","emoji":"▶️","platforms":["youtube_shorts","tiktok"],"angle":"algorithm hacks for faceless channels"},
       {"name":"Affiliate Atlas","handle":"affiliate.atlas","emoji":"🔗","platforms":["tiktok","youtube_shorts"],"angle":"affiliate marketing case studies"},
       {"name":"Digital Products 101","handle":"digital.products","emoji":"📲","platforms":["instagram","tiktok"],"angle":"sell digital downloads without inventory"},
       {"name":"Remote Job Finds","handle":"remote.funds","emoji":"🏠","platforms":["tiktok","linkedin"],"angle":"high-paying remote jobs, weekly lists"},
     ]},

    # --- HEALTH / BODY ---
    {"slug":"fitness","emoji":"💪","name":"Fitness & home workouts",
     "accounts":[
       {"name":"Home Gains","handle":"home.gains","emoji":"🏋️","platforms":["instagram","tiktok","youtube_shorts"],"angle":"no-equipment home workouts"},
       {"name":"No Gym Fit","handle":"nogym.fit","emoji":"💪","platforms":["tiktok","instagram"],"angle":"bodyweight-only programs"},
       {"name":"Protein Kitchen","handle":"protein.kitchen","emoji":"🥗","platforms":["instagram","tiktok"],"angle":"high-protein, low-effort meals"},
       {"name":"Couch to 5k","handle":"couch25k","emoji":"🏃","platforms":["youtube_shorts","instagram"],"angle":"beginner running plans"},
       {"name":"Mobility Fix","handle":"mobility.fix","emoji":"🧘","platforms":["instagram","tiktok"],"angle":"5-min mobility routines for desk workers"},
     ]},
    {"slug":"weight_loss","emoji":"⚖️","name":"Weight loss & nutrition",
     "accounts":[
       {"name":"Calorie Hacks","handle":"calorie.hacks","emoji":"🥗","platforms":["tiktok","instagram"],"angle":"low-calorie food swaps"},
       {"name":"Meal Prep Queen","handle":"mealprep.q","emoji":"🍱","platforms":["instagram","tiktok"],"angle":"Sunday meal prep in 60 minutes"},
       {"name":"Fat Loss Facts","handle":"fatloss.facts","emoji":"🔥","platforms":["tiktok","youtube_shorts"],"angle":"evidence-based fat loss vs myths"},
       {"name":"Sugar Free Me","handle":"sugar.free","emoji":"🚫","platforms":["instagram","tiktok"],"angle":"hidden sugar traps, clean swaps"},
       {"name":"Intermittent Fast","handle":"fast.daily","emoji":"⏱️","platforms":["tiktok","youtube_shorts"],"angle":"intermittent fasting for beginners"},
     ]},
    {"slug":"skincare","emoji":"✨","name":"Skincare & beauty",
     "accounts":[
       {"name":"Glow Up Daily","handle":"glowup.daily","emoji":"✨","platforms":["instagram","tiktok"],"angle":"affordable skincare routines"},
       {"name":"Skin Science","handle":"skin.science","emoji":"🔬","platforms":["youtube_shorts","instagram"],"angle":"evidence-based product reviews"},
       {"name":"Budget Glow","handle":"budget.glow","emoji":"💄","platforms":["tiktok","instagram"],"angle":"drugstore dupes for premium products"},
       {"name":"Acne Diaries","handle":"acne.diaries","emoji":"🧴","platforms":["tiktok","instagram"],"angle":"honest journeys + what worked"},
       {"name":"SPF Everything","handle":"spf.daily","emoji":"☀️","platforms":["instagram","tiktok"],"angle":"sunscreen reviews and application tips"},
     ]},
    {"slug":"men_style","emoji":"👔","name":"Men's fashion & grooming",
     "accounts":[
       {"name":"Capsule Wardrobe Guy","handle":"capsule.guy","emoji":"👕","platforms":["instagram","tiktok"],"angle":"15 items = 100 outfits"},
       {"name":"Budget Grooming","handle":"budget.groom","emoji":"🧔","platforms":["tiktok","youtube_shorts"],"angle":"affordable men's grooming"},
       {"name":"Date Fit Check","handle":"date.fit","emoji":"👔","platforms":["tiktok","instagram"],"angle":"outfit ideas for every occasion"},
       {"name":"Fragrance Finds","handle":"scent.finds","emoji":"🌬️","platforms":["tiktok","youtube_shorts"],"angle":"best colognes by budget"},
       {"name":"Sneaker Score","handle":"sneaker.score","emoji":"👟","platforms":["tiktok","instagram"],"angle":"sneaker drops and deals"},
     ]},

    # --- HOME / LIFE ---
    {"slug":"cooking","emoji":"🍳","name":"Quick cooking & recipes",
     "accounts":[
       {"name":"10 Min Meals","handle":"10min.meals","emoji":"⏱️","platforms":["instagram","tiktok","youtube_shorts"],"angle":"10-minute recipes, 5 ingredients or less"},
       {"name":"Student Kitchen","handle":"student.kitchen","emoji":"🍜","platforms":["tiktok","instagram"],"angle":"dorm and microwave cooking"},
       {"name":"Protein Plate","handle":"protein.plate","emoji":"🥩","platforms":["instagram","tiktok"],"angle":"high-protein, low-calorie meals"},
       {"name":"Budget Bites","handle":"budget.bites","emoji":"🥪","platforms":["tiktok","youtube_shorts"],"angle":"meals under $3 per serving"},
       {"name":"Air Fryer Life","handle":"airfryer.life","emoji":"🍟","platforms":["instagram","tiktok"],"angle":"air fryer everything"},
     ]},
    {"slug":"home_hacks","emoji":"🏠","name":"Home hacks & organization",
     "accounts":[
       {"name":"Dollar Tree Hacks","handle":"dollartree.hacks","emoji":"💵","platforms":["tiktok","instagram"],"angle":"$1 home organization finds"},
       {"name":"Small Space Living","handle":"small.spaces","emoji":"🏙️","platforms":["instagram","tiktok"],"angle":"apartment organization and decor"},
       {"name":"Clean With Me","handle":"clean.daily","emoji":"🧼","platforms":["tiktok","youtube_shorts"],"angle":"speed cleaning motivation"},
       {"name":"Renter Friendly","handle":"renter.friendly","emoji":"🔨","platforms":["tiktok","instagram"],"angle":"no-drill renter upgrades"},
       {"name":"IKEA Hack Lab","handle":"ikea.hacks","emoji":"🪑","platforms":["instagram","tiktok"],"angle":"IKEA furniture upgrades"},
     ]},
    {"slug":"pets","emoji":"🐾","name":"Pets & animals",
     "accounts":[
       {"name":"Dog Training Tips","handle":"dog.training","emoji":"🐕","platforms":["tiktok","instagram","youtube_shorts"],"angle":"30-second dog training fixes"},
       {"name":"Cat Facts Daily","handle":"cat.facts","emoji":"🐈","platforms":["tiktok","instagram"],"angle":"weird cat facts + behavior tips"},
       {"name":"Puppy Parenting","handle":"puppy.parent","emoji":"🐶","platforms":["instagram","tiktok"],"angle":"first-week puppy survival"},
       {"name":"Pet Budget Finds","handle":"pet.finds","emoji":"🦴","platforms":["tiktok"],"angle":"best pet products under $20"},
       {"name":"Rescue Stories","handle":"rescue.pets","emoji":"❤️","platforms":["tiktok","youtube_shorts"],"angle":"emotional rescue wins, viral pet clips"},
     ]},
    {"slug":"travel","emoji":"✈️","name":"Travel hacks & cheap flights",
     "accounts":[
       {"name":"Flight Hacker","handle":"flight.hacker","emoji":"✈️","platforms":["tiktok","instagram"],"angle":"mistake fares, points hacks"},
       {"name":"Carry On Only","handle":"carryon.only","emoji":"🎒","platforms":["instagram","tiktok"],"angle":"pack a week in a carry-on"},
       {"name":"Budget Country Guide","handle":"budget.country","emoji":"🌍","platforms":["youtube_shorts","tiktok"],"angle":"one country per week, $50/day budgets"},
       {"name":"Hidden Gems","handle":"hidden.gems","emoji":"🗺️","platforms":["tiktok","instagram"],"angle":"underrated spots over tourist traps"},
       {"name":"Digital Nomad Daily","handle":"nomad.daily","emoji":"💻","platforms":["tiktok","x"],"angle":"best cities for nomads this month"},
     ]},

    # --- TECH / BIZ ---
    {"slug":"saas","emoji":"🚀","name":"SaaS, startups & indie hacking",
     "accounts":[
       {"name":"Indie Hackers Daily","handle":"indie.daily","emoji":"🚀","platforms":["x","linkedin","youtube_shorts"],"angle":"revenue numbers, launch wins"},
       {"name":"Micro SaaS Lab","handle":"microsaas.lab","emoji":"🔧","platforms":["x","youtube_shorts"],"angle":"build SaaS without coding"},
       {"name":"Launch Log","handle":"launch.log","emoji":"📊","platforms":["x","linkedin"],"angle":"launch teardowns, pricing fixes"},
       {"name":"Pricing Teardown","handle":"pricing.teardown","emoji":"💲","platforms":["linkedin","youtube_shorts"],"angle":"pricing pages analysed in 30s"},
       {"name":"Cold Outbound AI","handle":"outbound.ai","emoji":"✉️","platforms":["linkedin","x"],"angle":"cold email + AI, replies guaranteed"},
     ]},
    {"slug":"ecommerce","emoji":"🛒","name":"Ecommerce & dropshipping",
     "accounts":[
       {"name":"Winning Products","handle":"winning.products","emoji":"🏆","platforms":["tiktok","youtube_shorts"],"angle":"products going viral this week"},
       {"name":"Shopify Starter","handle":"shopify.start","emoji":"🛍️","platforms":["youtube_shorts","tiktok"],"angle":"launch a store in a weekend"},
       {"name":"Ad Library Spy","handle":"ad.spy","emoji":"👀","platforms":["tiktok","youtube_shorts"],"angle":"ads currently printing money"},
       {"name":"Printful Profits","handle":"printful.profits","emoji":"👕","platforms":["tiktok","instagram"],"angle":"print-on-demand winners"},
       {"name":"Amazon FBA Finds","handle":"fba.finds","emoji":"📦","platforms":["youtube_shorts"],"angle":"FBA product research breakdowns"},
     ]},
    {"slug":"coding","emoji":"💻","name":"Coding & dev tools",
     "accounts":[
       {"name":"VS Code Tricks","handle":"vscode.tricks","emoji":"⌨️","platforms":["tiktok","youtube_shorts","x"],"angle":"VS Code shortcuts you missed"},
       {"name":"Git in 60s","handle":"git.daily","emoji":"🔀","platforms":["x","youtube_shorts"],"angle":"Git explained in 60 seconds"},
       {"name":"Junior Dev Tips","handle":"junior.dev","emoji":"🐣","platforms":["tiktok","youtube_shorts"],"angle":"what I wish I knew as a junior"},
       {"name":"AI Code Review","handle":"ai.code","emoji":"🤖","platforms":["youtube_shorts","x"],"angle":"AI coding tools that actually help"},
       {"name":"Framework Fight","handle":"framework.fight","emoji":"🥊","platforms":["x","youtube_shorts"],"angle":"React vs Vue vs Svelte in 60 seconds"},
     ]},

    # --- PSYCHOLOGY / SELF ---
    {"slug":"psychology","emoji":"🧠","name":"Psychology & human behavior",
     "accounts":[
       {"name":"Dark Psychology Hub","handle":"dark.psych","emoji":"🎭","platforms":["tiktok","youtube_shorts"],"angle":"manipulation tactics to recognize"},
       {"name":"Body Language 101","handle":"body.language","emoji":"👀","platforms":["tiktok","instagram"],"angle":"read anyone instantly"},
       {"name":"Cognitive Biases Daily","handle":"bias.daily","emoji":"🧩","platforms":["youtube_shorts","x"],"angle":"one bias per day, explained"},
       {"name":"Persuasion Hacks","handle":"persuasion.hacks","emoji":"🗣️","platforms":["linkedin","tiktok"],"angle":"get people to say yes"},
       {"name":"Stoic Daily","handle":"stoic.daily","emoji":"📜","platforms":["instagram","tiktok"],"angle":"stoic wisdom in 60 seconds"},
     ]},
    {"slug":"productivity","emoji":"⚡","name":"Productivity & self-improvement",
     "accounts":[
       {"name":"Notion Hacks","handle":"notion.hacks","emoji":"📓","platforms":["tiktok","youtube_shorts"],"angle":"one Notion trick per post"},
       {"name":"Deep Work Daily","handle":"deep.work","emoji":"🎯","platforms":["youtube_shorts","x"],"angle":"focus hacks backed by studies"},
       {"name":"Morning Routine Wins","handle":"am.routine","emoji":"🌅","platforms":["instagram","tiktok"],"angle":"routines of top performers"},
       {"name":"Quit Bad Habits","handle":"quit.habits","emoji":"🚭","platforms":["tiktok","youtube_shorts"],"angle":"dopamine reset, habit loops"},
       {"name":"One Book A Week","handle":"one.book","emoji":"📚","platforms":["tiktok","instagram"],"angle":"one book insight per post"},
     ]},
    {"slug":"dating","emoji":"❤️","name":"Dating & relationships",
     "accounts":[
       {"name":"Text Game Tips","handle":"text.game","emoji":"📱","platforms":["tiktok","instagram"],"angle":"texts that get replies"},
       {"name":"Body Language of Attraction","handle":"attraction.signs","emoji":"👀","platforms":["tiktok"],"angle":"signs they are into you"},
       {"name":"Red Flags Daily","handle":"red.flags","emoji":"🚩","platforms":["tiktok","instagram"],"angle":"dating red flags people ignore"},
       {"name":"First Date Fix","handle":"first.date","emoji":"🍷","platforms":["tiktok"],"angle":"first date mistakes to avoid"},
       {"name":"Healthy Relationship Tips","handle":"healthy.couple","emoji":"💞","platforms":["instagram","tiktok"],"angle":"communication habits that keep couples together"},
     ]},

    # --- MISC CREATOR-HIGH-CPM ---
    {"slug":"gaming","emoji":"🎮","name":"Gaming tips & easter eggs",
     "accounts":[
       {"name":"Easter Egg Hunt","handle":"ee.hunt","emoji":"🥚","platforms":["tiktok","youtube_shorts"],"angle":"hidden details you missed"},
       {"name":"Pro Settings","handle":"pro.settings","emoji":"⚙️","platforms":["tiktok","youtube_shorts"],"angle":"controller settings pro players use"},
       {"name":"Clips That Broke The Game","handle":"broken.game","emoji":"💥","platforms":["tiktok","youtube_shorts"],"angle":"glitches and broken mechanics"},
       {"name":"Indie Gem Finds","handle":"indie.gems","emoji":"💎","platforms":["tiktok","youtube_shorts"],"angle":"underrated games nobody plays"},
       {"name":"Speedrun Highlights","handle":"speedrun.wins","emoji":"⏱️","platforms":["youtube_shorts","tiktok"],"angle":"world record clips explained"},
     ]},
    {"slug":"real_estate","emoji":"🏠","name":"Real estate investing",
     "accounts":[
       {"name":"House Hack 101","handle":"house.hack","emoji":"🏘️","platforms":["tiktok","youtube_shorts"],"angle":"live for free by house hacking"},
       {"name":"Airbnb Income Lab","handle":"airbnb.lab","emoji":"🛏️","platforms":["instagram","tiktok"],"angle":"short-term rental wins"},
       {"name":"Whipping Wholesaling","handle":"whole.saling","emoji":"🤝","platforms":["youtube_shorts"],"angle":"wholesaling step by step"},
       {"name":"REITs Simplified","handle":"reit.simple","emoji":"📊","platforms":["youtube_shorts","x"],"angle":"passive real estate without being a landlord"},
       {"name":"First Home Buyer","handle":"first.home","emoji":"🔑","platforms":["tiktok","instagram"],"angle":"first home mistakes to avoid"},
     ]},
    {"slug":"luxury","emoji":"💎","name":"Luxury lifestyle (aspirational)",
     "accounts":[
       {"name":"Billionaire Habits","handle":"billionaire.habits","emoji":"🤑","platforms":["tiktok","youtube_shorts"],"angle":"habits of ultra-wealthy people"},
       {"name":"Watch of the Day","handle":"watch.daily","emoji":"⌚","platforms":["instagram","tiktok"],"angle":"iconic watches explained"},
       {"name":"Supercar Spotter","handle":"supercar.spot","emoji":"🏎️","platforms":["tiktok","youtube_shorts"],"angle":"supercars spotted on the street"},
       {"name":"Mansion Tour Daily","handle":"mansion.tour","emoji":"🏰","platforms":["tiktok","youtube_shorts"],"angle":"crazy homes and interiors"},
       {"name":"First Class Flights","handle":"first.class","emoji":"🛫","platforms":["instagram","tiktok"],"angle":"luxury travel reviews"},
     ]},
    {"slug":"motivation","emoji":"🔥","name":"Motivation & mindset",
     "accounts":[
       {"name":"Hustle Quotes Daily","handle":"hustle.q","emoji":"💯","platforms":["instagram","tiktok"],"angle":"raw, unapologetic grind quotes"},
       {"name":"Comeback Stories","handle":"comeback.story","emoji":"🦁","platforms":["tiktok","youtube_shorts"],"angle":"rags to riches in 60 seconds"},
       {"name":"Discipline > Motivation","handle":"discipline.daily","emoji":"⛓️","platforms":["tiktok","instagram"],"angle":"daily discipline reminders"},
       {"name":"Sigma Rules","handle":"sigma.rules","emoji":"🐺","platforms":["tiktok","youtube_shorts"],"angle":"unbothered male mindset clips"},
       {"name":"Millionaire Mindset","handle":"millionaire.mind","emoji":"💭","platforms":["tiktok","instagram"],"angle":"money psychology that changed everything"},
     ]},
]
