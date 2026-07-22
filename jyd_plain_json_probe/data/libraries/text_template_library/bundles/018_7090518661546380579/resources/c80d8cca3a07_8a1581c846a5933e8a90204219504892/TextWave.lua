local exports = exports or {}
local TextWave = TextWave or {}
TextWave.__index = TextWave
function TextWave.new(construct, ...)
    local self = setmetatable({}, TextWave)
	self.duration = 0.5
	self.lasttime= 0
	self.height = 24
	self.length = 0.3

	self.cliptime = 0.15
	self.preCliptime = 0.15

	self.fixClipTime = 0.15
	-- print("New")
	self.tweenDirty = true
	self.tweens={}
	self.alpha={}
    if construct and TextWave.constructor then TextWave.constructor(self, ...) end
    return self
end

function TextWave:constructor()

end

function TextWave:quadOut(t, b, c, d)
	t = t / d
	return -c * t * (t - 2) + b
end


function TextWave:linearFunc(t,ratio,init)
	return ratio*t+init
end

function TextWave:ElasticOut(t, b, c, d)
	t=t/d
	if t~=0.0 and t~=1.0 then
		t = math.exp(-10.0 * t) * math.sin((t - 0.075) * (2.0*math.pi) / 0.3) + 1.0
	end
	return self:linearFunc(t,c,b)
end
	   

function TextWave:realLineFunc(t, b, c, d)
	return self:quadOut(t, b, c, d)
end

function TextWave:initAlpha()
	self.text = self.comp.entity:getComponent('SDFText')
    if self.text == nil then
        local text = self.comp.entity:getComponent('Text')
        if text ~= nil then
			self.text = self.comp.entity:addComponent('SDFText')
            self.text:setTextWrapper(text)
        end
    end 
	
	local text = self.text
	local chars = text.chars
	local count = chars:size()
	for i = 0, count - 1 do
		local char = chars:get(i)
		self.alpha[i+1] = 0
	end
end

function TextWave:onStart(comp) 
	self.comp = comp
	self:initAlpha()
end

function TextWave:checkDirty()
	self.tweens = {}
	local text = self.text
	local chars = text.chars
	local count = chars:size()

	local timePercent = self.time/(self.duration+0.001)
	-- Amaz.LOGI("======>wdg2",self.cliptime.."||"..self.time.."||"..self.duration)

	for i = 0, count - 1 do
		local char = chars:get(i)

		-- local rd_num = self:realLineFunc(self.time,100,100,self.duration)
		local endalpha = math.random(0,20+timePercent*80)/100
		if self.alpha[i+1] >0.8 then
			endalpha = math.random(0,10+timePercent*20)/100
		elseif self.alpha[i+1] <0.3 then
			endalpha = math.random(0,20+timePercent*80)/100
		end


		-- endalpha = endalpha/100
		endalpha = endalpha > 1.0 and 1.0 or endalpha
		local duration = self.cliptime
		-- local oneFps = 0.033
		-- if math.abs(self.time - self.duration) > 0 and math.abs(self.time - self.duration) < (self.cliptime+oneFps) then
		-- 	duration = self.duration - self.time
		-- 	endalpha = 1.0
		-- end

		table.insert(self.tweens,self.text.entity.scene.tween:fromTo(char, 
		{["color"] =  Amaz.Vector4f(char.color.x,char.color.y,char.color.z,self.alpha[i+1])},
		{["color"] = Amaz.Vector4f(char.color.x,char.color.y,char.color.z,endalpha)},
		duration,
		Amaz.Ease.linear,
		nil,
		0,
		nil,
		false
		))
		--char.color = Amaz.Vector4f(char.color.x,char.color.y,char.color.z,math.random());
		--char.color=Amaz.Vector4f(1.,0.,0.,1.)
		self.alpha[i+1] = endalpha
	end
	
end

function TextWave:seek(time)
	self.time = time

	local text = self.text
	local chars = text.chars
	self.text.chars = chars

	if chars:size() ~= #self.tweens then
		self:checkDirty()
	end

	if self.duration <= 0.0001 then
		return
	end
	if self.time < 0.033 then
		for key, value in pairs(self.tweens) do
			value:set(self.cliptime)
			value:clear()
		end 

		self:initAlpha()
		local chars = text.chars
		local count = chars:size()
		for i = 0, count - 1 do
			local char = chars:get(i)
			if char.rowth ~= -1 then
				char.color = Amaz.Vector4f(char.color.x,char.color.y,char.color.z,0.0)
			end
		end
		return
	end
	for key, value in pairs(self.tweens) do
		--if (time%(self.length*self.duration))<self.length*self.duration and (time%(self.length*self.duration))>0 then
		value:set(time-self.lasttime)
	end
	local oneFps = 0.033
	self.preCliptime = (self.fixClipTime - oneFps)*self.duration + oneFps
   	self.preCliptime = self.preCliptime > self.fixClipTime and self.fixClipTime or self.preCliptime


	local passDuration = time/(self.duration)

	-- self.cliptime = self.preCliptime - self.preCliptime *0.5*time/(self.duration+0.001)
	if time < self.preCliptime then
		self.cliptime = self.preCliptime
	end
	-- Amaz.LOGI("0000000",time.."||"..self.lasttime.."||"..self.cliptime)
	if time - self.lasttime > self.cliptime or self.lasttime>time then
		self.tweenDirty = true
		for key, value in pairs(self.tweens) do
			value:set(self.cliptime)
		end
		self.cliptime = self:realLineFunc(time,self.preCliptime,2.0*oneFps-self.preCliptime,self.duration)--self.preCliptime - (self.preCliptime -oneFps)*passDuration*passDuration*passDuration
		self:checkDirty()
		self.lasttime = time
	end

	local chars = text.chars
	local count = chars:size()
	for i = 0, count - 1 do
		local char = chars:get(i)
		if char.rowth ~= -1 then
			local alpha = char.color.w*(1.0-passDuration*passDuration*passDuration*passDuration) + passDuration*passDuration*passDuration*passDuration
			if passDuration < 0.2 then
				alpha = alpha*passDuration/0.2
			end 
			char.color = Amaz.Vector4f(char.color.x,char.color.y,char.color.z,alpha)
		end
	end

end

function TextWave:setDuration(duration)
   self.duration = duration
   local oneFps = 0.033
   self.preCliptime = (self.fixClipTime - oneFps)*duration + oneFps
   self.preCliptime = self.preCliptime > self.fixClipTime and self.fixClipTime or self.preCliptime
   self.cliptime = self.preCliptime 

end

function TextWave:resetData()
	self.tweenDirty = true
	for key, value in pairs(self.tweens) do
    	value:set(self.cliptime)
        value:clear()
    end 
    self.tweens = {}
	local text = self.text
	if text ~= nil then
		local chars = text.chars
		local count = chars:size()
		for i = 0, count - 1 do
			local char = chars:get(i)
			if char.rowth ~= -1 then
				 char.color = Amaz.Vector4f(char.color.x,char.color.y,char.color.z,1.0)
			end
		end
		self.text.chars = chars
	end
end
function TextWave:clear()
	self:resetData()
end


function TextWave:onLeave()
	self:resetData()
end

exports.TextWave = TextWave
return exports
