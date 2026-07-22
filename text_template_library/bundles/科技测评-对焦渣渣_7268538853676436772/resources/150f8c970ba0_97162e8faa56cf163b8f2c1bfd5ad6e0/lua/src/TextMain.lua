local Utils = require("common/Utils")
local Helper = require("info_sticker/Helper")
local AEAdapter = require("common/AEAdapter")
local AE = require("AE")

local BLUR_DURATION = 14 / 30
local CHAR_DURATION = 18 / 30

local trace = Utils.trace

local TextMain = {}
TextMain.__index = TextMain
function TextMain.new ()
    return setmetatable({}, TextMain)
end

function TextMain:onCreate (env)
    self.ae = AEAdapter:new()
    self.ae:addKeyframes("blur", AE.blur)
    self.ae:addKeyframes("char", AE.char)

    self.materials = Amaz.Vector()
    self.materials:pushBack(env.material:instantiate())
    self.renderer = env.rootNode.entity:getComponent("MeshRenderer")
    self.renderer.materials = self.materials

    ---#ifdef DEV
--//    env.rootTextOld.fontSize = 15
--//    env.rootTextOld.str = [[AAAAAAAA
--//AAAAAAAAAAAA
--//AAAAAAAAAAAAAAAA
--//AAAAAAAAAAAAAAAAAAAA
--//AAAAAAAAAAAAAAAAAAAAAAAA]]
--//    env.duration = 1
    ---#endif
end

function TextMain:onShow (env)

end

function TextMain:onHide (env)
    local text = env.rootTextOld
    text.renderToRT = false
    local chars = text.chars
    for i = 0, chars:size() - 1 do
        local char = chars:get(i)
        char.position = char.initialPosition:copy()
        char.scale = Amaz.Vector3f(1, 1, 1)
        char.rotate = Amaz.Vector3f(0, 0, 0)
        char.anchor = Amaz.Vector2f(0, 0)
    end
end

function TextMain:onChange (env)
    local text = env.rootTextOld
    text.targetRTExtraSize = Amaz.Vector2f(text.rect.width * 2, text.rect.height * 2)
    text.renderToRT = true
    self.renderer.materials = self.materials
    text:forceTypeSetting()
    self.lines = Helper.splitByLine(text.chars)
    for _, line in ipairs(self.lines) do
        local left = 9999
        local right = -9999
        local count = 0
        for _, char in ipairs(line) do
            char.anchor = Amaz.Vector2f(0, -char.height * 0.3)
            left = math.min(left, char.position.x)
            right = math.max(right, char.position.x)
            count = count + 1
        end
        line.count = count
        line.left = left
        line.right = right
    end

    local material = self.materials:get(0)
    material:setVec2("screenSize", text.targetRTExtraSize)
    material:setVec2("direction", Amaz.Vector2f(math.cos(math.rad(30)), math.sin(math.rad(30))))
end

function TextMain:onUpdate (env, elapsed)
    local text = env.rootTextOld
    local lines = self.lines
    if not lines or #lines == 0 then
        return
    end

    local totalDelay = 0
    local totalDuration = 0
    for i = 1, #lines do
        local lineDuration = (#lines[i] - 1) / 30 + CHAR_DURATION
        lines[i].start = totalDelay
        lines[i].duration = lineDuration
        totalDuration = math.max(totalDuration, totalDelay + lineDuration)

        totalDelay = totalDelay + lineDuration * 0.1
    end

    local rate = totalDuration / env.duration
    elapsed = elapsed * rate

    local fontScale = Helper.getFontSize(env.rootText, env.rootTextOld, 20) / 20
    local blur = self.ae:get("blur/ADBE Motion Blur-0002", elapsed)[1] * fontScale * text.rect.height / #lines / 3000
    for i = 1, #lines do
        local line = lines[i]

        local lineWidth = line.right - line.left
        local mt = elapsed - line.start

        for j = 1, #line do
            local char = line[j]
            local t = mt - (j - 1) / 30

            local sx = 0
            local sy = 0
            local ox = 0
            local oy = 0
            local rz = 0
            if t <= 0 then
                sx = 0
                sy = 0
                ox = 0
                oy = 0
                rz = 0
            elseif t < CHAR_DURATION then
                sx = self.ae:get("char/ADBE Scale", t)[1] * 0.01
                sy = self.ae:get("char/ADBE Scale", t)[2] * 0.01
                ox = self.ae:get("char/ADBE Position_0", t)[1] - 198
                oy = self.ae:get("char/ADBE Position_1", t)[1] - 321.5
                rz = -self.ae:get("char/ADBE Rotate Z", t)[1]

                ox = ox * fontScale * lineWidth / 500
                oy = oy * fontScale * 1.5
            else
                sx = 1
                sy = 1
                ox = 0
                oy = 0
                rz = 0
            end

            local p = char.initialPosition
            p.x = p.x + ox
            p.y = p.y - oy
            p.y = p.y + char.height * 0.3 * (sy - 1)
            char.position = p
            char.scale = Amaz.Vector3f(sx, sy, 1)
            char.rotate = Amaz.Vector3f(0, 0, rz)
        end
    end

    local material = self.materials:get(0)
    material:setFloat("blurStep", blur)
end

return TextMain
