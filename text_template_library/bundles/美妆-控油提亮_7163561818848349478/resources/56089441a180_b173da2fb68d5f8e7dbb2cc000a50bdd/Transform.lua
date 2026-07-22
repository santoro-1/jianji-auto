local exports = exports or {}
local Transform = Transform or {}
Transform.__index = Transform
function Transform.new(construct, ...)
    local self = setmetatable({}, Transform)
    self.text = nil
    self.lines = {}
    self.linesCnt = 0
    self.duration = 3.0
    self.extraSpacing = 0.43
    if construct and Transform.constructor then Transform.constructor(self, ...) end
    return self
end

function Transform:constructor()

end

function Transform:onStart(comp)
    self.text = comp.entity:getComponent('SDFText')
    if self.text == nil then
        local text = comp.entity:getComponent('Text')
        if text ~= nil then
			self.text = comp.entity:addComponent('SDFText')
            self.text:setTextWrapper(text)
        end
    end
	self.richText = comp.entity:getComponent("Text")
end

function Transform:onEnter()
    if self.richText then
        self.initLetterSpacing = self.richText.typeSettingParam.letterSpacing
    else
        self.initLetterSpacing = self.text.wordGap
    end
end

function Transform:seek(time)
    local progress = Amaz.Ease.CubicOut(time, 0, 1, self.duration)
    local alphaTime = 0.2 -- 
    local alpha = progress / alphaTime
    if alpha > 1 then alpha = 1 end

    if self.richText then
        self.richText.typeSettingParam.letterSpacing = self.initLetterSpacing + self.extraSpacing * (1.0 - progress)
        for i = 1, self.richText.letters:size() do
            local letter = self.richText.letters:get(i - 1)
            letter.instanceColor = Amaz.Color(1, 1, 1, alpha)
        end
    else
        self.text.wordGap = self.initLetterSpacing + self.extraSpacing * (1.0 - progress)
        for i = 1, self.text.chars:size() do
            local letter = self.text.chars:get(i - 1)
            letter.color.w = alpha
        end

    end
end

function Transform:setDuration(duration)
   self.duration = duration
end

function Transform:clear()
    if self.initLetterSpacing ~= nil then
        if self.richText then
            self.richText.typeSettingParam.letterSpacing = self.initLetterSpacing
        else
            self.text.wordGap = self.initLetterSpacing

        end
    end
    if self.richText then
        for i = 1, self.richText.letters:size() do
            local letter = self.richText.letters:get(i - 1)
            letter.instanceColor = Amaz.Color(1, 1, 1, 1)
        end
    else
        for i = 1, self.text.chars:size() do
            local letter = self.text.chars:get(i - 1)
            letter.color.w = 1
        end
    end
end
function Transform:onLeave()
    if self.initLetterSpacing ~= nil then
        if self.richText then
            self.richText.typeSettingParam.letterSpacing = self.initLetterSpacing
        else
            self.text.wordGap = self.initLetterSpacing

        end
    end
    if self.richText then
        for i = 1, self.richText.letters:size() do
            local letter = self.richText.letters:get(i - 1)
            letter.instanceColor = Amaz.Color(1, 1, 1, 1)
        end
    else
        for i = 1, self.text.chars:size() do
            local letter = self.text.chars:get(i - 1)
            letter.color.w = 1
        end
    end
end

exports.Transform = Transform
return exports
