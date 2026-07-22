local Utils = require("common/Utils")
local AEAdapter = require("common/AEAdapter")
local Helper = require("info_sticker/Helper")
local AE = require("AE")


local TextMain = {}
TextMain.__index = TextMain
function TextMain.new ()
    local self = setmetatable({}, TextMain)
    self.TIME_S = 7/30
    self.TIME_E = 23/30
    self.DURATION = self.TIME_E - self.TIME_S
    self.INTERVAL = 2/30
    self.AE = AE
    return self
end


function TextMain:onCreate (env)
    ---#ifdef DEV
--//    env.rootTextOld.fontSize = 24
--//    env.rootTextOld.str = "First Line\n今日穿搭"
--//    env.duration = 20
    ---#endif

    self.ae = AEAdapter:new()
    self.ae:addKeyframes("", self.AE)
end

function TextMain:onShow (env)
end

function TextMain:onHide (env)
    local chars = env.rootTextOld.chars
    for i = 0, chars:size() - 1 do
        local char = chars:get(i)
        char.position = char.initialPosition
        char.scale = Amaz.Vector3f(1, 1, 1)
        char.rotate = Amaz.Vector3f(0, 0, 0)
        char.color = Amaz.Vector4f(1, 1, 1, 1)
    end
end

function TextMain:onChange (env)
    local text = env.rootTextOld
    text:forceTypeSetting()
    self.chars = Helper.splitByChar(text.chars)
end

function TextMain:onUpdate (env, elapsed)
    if not self.chars then
        return
    end

    local chars = self.chars
    local count = #chars
    local designDuration = self.DURATION + self.INTERVAL * (count - 1)
    local timeScale = designDuration / env.duration
    local designElapsed = elapsed * timeScale

    for i, char in ipairs(chars) do
        char = char[1]
        local t0 = self.INTERVAL * (i - 1)
        local t1 = t0 + self.DURATION
        local t = Utils.step(t0, t1, designElapsed)
        t = Utils.mix(self.TIME_S, self.TIME_E, t)
        local r = -self.ae:get("/ADBE Rotate Z_21", t)[1]
        char.rotate = Amaz.Vector3f(0, 0, r)
        local a = self.ae:get("/ADBE Opacity_22", t)[1] * 0.01
        char.color = Amaz.Vector4f(1, 1, 1, a)
        local s = self.ae:get("/ADBE Scale_17", t)[1] * 0.01
        char.scale = Amaz.Vector3f(s, 1, 1)
        local p0 = char.initialPosition
        local hh = char.height * 0.5
        local rr = hh * 0.75
        local ax = p0.x
        local ay = p0.y - rr
        r = math.rad(r + 90)
        local dx = math.cos(r) * rr
        local dy = math.sin(r) * rr
        char.position = Amaz.Vector3f(ax + dx, ay + dy, p0.y)
    end
end


return TextMain